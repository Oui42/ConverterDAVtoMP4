"""Zamiana nagrań DAV z rejestratorów na MP4.

Obsługiwane:
- JUAN/JuFeng (plik zaczyna się od „JUFEN”) – własny parser, obraz H.264/H.265 bez ponownego kodowania,
- Dahua i inne, które zna ffmpeg – najpierw bez utraty jakości, w razie błędu kodowanie od nowa (H.264).

Bez okna:  python converter.py plik.dav|folder [...]
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# komunikaty dla użytkownika: klucz → {język: tekst}
MESSAGES = {
    "no_ffmpeg": {"pl": "Brakuje programu ffmpeg potrzebnego do zamiany filmów.",
                  "en": "The ffmpeg program needed to convert videos is missing."},
    "no_frames": {"pl": "W tym pliku nie ma obrazu – może być pusty albo uszkodzony.",
                  "en": "This file contains no video – it may be empty or damaged."},
    "write_failed": {"pl": "Nie udało się zapisać filmu.",
                     "en": "The video could not be saved."},
    "unreadable": {"pl": "Nie udało się odczytać nagrania – plik może być uszkodzony "
                         "albo pochodzić z nietypowego rejestratora.",
                   "en": "The recording could not be read – the file may be damaged "
                         "or come from an unusual recorder."},
    "not_found": {"pl": "Nie znaleziono pliku – mógł zostać przeniesiony albo usunięty.",
                  "en": "File not found – it may have been moved or deleted."},
    "no_space": {"pl": "Za mało miejsca na dysku, żeby zapisać film.",
                 "en": "Not enough disk space to save the video."},
    "no_access": {"pl": "Brak dostępu do pliku albo folderu (może film jest otwarty w innym programie?).",
                  "en": "No access to the file or folder (is the video open in another program?)."},
    "unexpected": {"pl": "Nieoczekiwany błąd.", "en": "Unexpected error."},
}


class ConvertError(Exception):
    """Błąd z komunikatem zrozumiałym dla użytkownika (details = techniczne szczegóły)."""

    def __init__(self, key, details=""):
        super().__init__(MESSAGES[key]["pl"])
        self.key = key
        self.details = details

    def message(self, lang="pl"):
        return MESSAGES[self.key].get(lang) or MESSAGES[self.key]["pl"]


class Cancelled(Exception):
    pass


def ffmpeg_path():
    # w wersji .exe (PyInstaller) ffmpeg.exe leży obok programu
    for base in (getattr(sys, "_MEIPASS", None), Path(sys.executable).parent, Path(__file__).parent):
        if base and (Path(base) / "ffmpeg.exe").exists():
            return str(Path(base) / "ffmpeg.exe")
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise ConvertError("no_ffmpeg")


# --- Format „JUFEN2” (rejestratory JUAN/JuFeng) ---------------------------------------------
# Nagłówek pliku 0x400 bajtów, dalej pakiety: 00 00 01 E0|E1 (E1 = klatka kluczowa),
# długość danych (LE32), sekundy (LE32), milisekundy (LE16), 6 bajtów (bajt 14 = kodek, dalej
# rozdzielczość), potem ramka H.264/H.265 w postaci Annex-B. Ffmpeg tego nie czyta, więc
# przepakowujemy klatki do MPEG-TS z prawdziwymi znacznikami czasu (liczba klatek/s jest zmienna).

JUFEN_MAGIC = b"JUFEN"
JUFEN_DATA = 0x400
PKT_HDR = 20
MAX_GAP = 1.0  # s – dłuższa przerwa między klatkami to błąd znacznika czasu
VIDEO_PID, PMT_PID = 0x100, 0x1000
JUFEN_CODECS = {1: ("H.264", 0x1B), 2: ("H.265", 0x24)}  # bajt 14 → (kodek, stream_type w MPEG-TS)


def _crc32_mpeg(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc


def _psi_packet(pid, section):
    section += _crc32_mpeg(section).to_bytes(4, "big")
    body = b"\x00" + section  # pointer_field
    return bytes([0x47, 0x40 | pid >> 8, pid & 0xFF, 0x10]) + body + b"\xff" * (184 - len(body))


PAT = _psi_packet(0, bytes([0x00, 0xB0, 0x0D, 0x00, 0x01, 0xC1, 0x00, 0x00,
                            0x00, 0x01, 0xE0 | PMT_PID >> 8, PMT_PID & 0xFF]))


def _pmt(stream_type):
    return _psi_packet(PMT_PID, bytes([0x02, 0xB0, 0x12, 0x00, 0x01, 0xC1, 0x00, 0x00,
                                       0xE0 | VIDEO_PID >> 8, VIDEO_PID & 0xFF, 0xF0, 0x00,
                                       stream_type, 0xE0 | VIDEO_PID >> 8, VIDEO_PID & 0xFF, 0xF0, 0x00]))


class TsWriter:
    """Minimalny zapis MPEG-TS: jeden strumień obrazu (H.264/H.265), PTS na każdą klatkę."""

    def __init__(self, out, stream_type):
        self.out = out
        self.psi = PAT + _pmt(stream_type)
        self.cc = 0

    def frame(self, data, pts, key):
        if key:
            self.out.write(self.psi)  # ciągłości liczników PSI nie pilnujemy – ffmpeg to toleruje
        p = pts
        pes = (b"\x00\x00\x01\xe0\x00\x00\x80\x80\x05" + bytes([
            0x21 | (p >> 29) & 0x0E, (p >> 22) & 0xFF, (p >> 14) & 0xFE | 1, (p >> 7) & 0xFF, (p << 1) & 0xFE | 1,
        ]) + data)
        pcr = max(pts - 9000, 0)
        af = bytes([7, 0x10 | (0x40 if key else 0),
                    (pcr >> 25) & 0xFF, (pcr >> 17) & 0xFF, (pcr >> 9) & 0xFF, (pcr >> 1) & 0xFF,
                    (pcr & 1) << 7 | 0x7E, 0x00])
        chunks, i, first = [], 0, True
        while i < len(pes):
            a = af if first else b""
            chunk = pes[i:i + 184 - len(a)]
            i += len(chunk)
            stuff = 184 - len(a) - len(chunk)
            if stuff:
                if a:
                    a = bytes([a[0] + stuff]) + a[1:] + b"\xff" * stuff
                elif stuff == 1:
                    a = b"\x00"
                else:
                    a = bytes([stuff - 1, 0x00]) + b"\xff" * (stuff - 2)
            chunks.append(bytes([0x47, (0x40 if first else 0) | VIDEO_PID >> 8, VIDEO_PID & 0xFF,
                                 (0x30 if a else 0x10) | self.cc]) + a + chunk)
            self.cc = (self.cc + 1) & 0x0F
            first = False
        self.out.write(b"".join(chunks))


def is_jufen(path):
    with open(path, "rb") as f:
        return f.read(len(JUFEN_MAGIC)) == JUFEN_MAGIC


def _convert_jufen(src, tmp, progress, cancel):
    with open(src, "rb") as f:
        f.seek(JUFEN_DATA + 14)
        b = f.read(1)
    codec, stream_type = JUFEN_CODECS.get(b[0] if b else 1, JUFEN_CODECS[1])
    # hvc1 – bez tego Windows/QuickTime nie odtwarzają H.265 z MP4
    tag = ["-tag:v", "hvc1"] if codec == "H.265" else []
    size = src.stat().st_size
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            [ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "mpegts", "-i", "pipe:0",
             "-map", "0:v:0", "-c:v", "copy", *tag, "-video_track_timescale", "90000",
             "-movflags", "+faststart", "-f", "mp4", str(tmp)],
            stdin=subprocess.PIPE, stderr=err, creationflags=NO_WINDOW)
        ts = TsWriter(proc.stdin, stream_type)
        frames = 0
        t_prev = last_pts = None
        clock, step = 0.0, 1 / 15
        try:
            with open(src, "rb") as f:
                f.seek(JUFEN_DATA)
                pos = JUFEN_DATA
                while True:
                    if cancel.is_set():
                        proc.kill()
                        proc.wait()
                        raise Cancelled()
                    hdr = f.read(PKT_HDR)
                    if len(hdr) < PKT_HDR:
                        break
                    if hdr[:3] != b"\x00\x00\x01":
                        # uszkodzony fragment – szukamy następnego pakietu
                        f.seek(pos + 1)
                        buf = f.read(4 * 1024 * 1024)
                        j = buf.find(b"\x00\x00\x01\xe1")
                        if j < 0:
                            j = buf.find(b"\x00\x00\x01\xe0")
                        if j < 0:
                            break
                        pos += 1 + j
                        f.seek(pos)
                        continue
                    length, sec, ms = struct.unpack_from("<IIH", hdr, 4)
                    data = f.read(length)
                    pos += PKT_HDR + length
                    if hdr[3] not in (0xE0, 0xE1) or len(data) < length:
                        continue
                    t = sec + ms / 1000
                    if t_prev is None:
                        if hdr[3] != 0xE1:
                            continue  # zaczynamy od klatki kluczowej
                    else:
                        # rejestrator co ~minutę wpisuje skok o ~4 s, choć klatek nie brakuje (zegar na obrazie
                        # idzie dalej równo) – skok > MAX_GAP albo cofnięcie = zwykły odstęp między klatkami
                        delta = t - t_prev
                        if 0 < delta <= MAX_GAP:
                            step = delta
                        clock += step
                    t_prev = t
                    pts = 90000 + round(clock * 90000)
                    if last_pts is not None and pts <= last_pts:
                        pts = last_pts + 1
                    last_pts = pts
                    ts.frame(data, pts, hdr[3] == 0xE1)
                    frames += 1
                    if frames % 50 == 0:
                        progress(pos / size)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass  # ffmpeg zakończył się wcześniej – powód będzie w err
        code = proc.wait()
        err.seek(0)
        details = err.read().decode("utf-8", "replace").strip()
    if not frames:
        raise ConvertError("no_frames", details)
    if code != 0:
        raise ConvertError("write_failed", details)
    return (last_pts - 90000) / 90000


# --- Pozostałe formaty (ffmpeg) -------------------------------------------------------------

def _duration(src):
    p = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(src)], capture_output=True, text=True,
                       errors="replace", creationflags=NO_WINDOW)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0


def _run_ffmpeg(args, total, progress, cancel):
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-nostats",
                                 "-progress", "pipe:1", *args],
                                stdout=subprocess.PIPE, stderr=err, text=True, errors="replace",
                                creationflags=NO_WINDOW)
        # przerwanie w osobnym wątku – odczyt stdout blokuje
        threading.Thread(target=lambda: (cancel.wait(), proc.poll() is None and proc.kill()), daemon=True).start()
        for line in proc.stdout:
            if line.startswith("out_time_us=") and total:
                try:
                    progress(int(line.split("=")[1]) / 1e6 / total)
                except ValueError:
                    pass
        code = proc.wait()
        err.seek(0)
        return code, err.read().decode("utf-8", "replace").strip()


def _convert_ffmpeg(src, tmp, progress, cancel):
    total = _duration(src)
    base = ["-fflags", "+genpts", "-i", str(src), "-map", "0:v:0", "-map", "0:a?"]
    out = ["-c:a", "aac", "-movflags", "+faststart", "-f", "mp4", str(tmp)]
    code, details = _run_ffmpeg(base + ["-c:v", "copy"] + out, total, progress, cancel)
    if code != 0 and not cancel.is_set():
        progress(0)
        code, details = _run_ffmpeg(base + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                                            "-pix_fmt", "yuv420p"] + out, total, progress, cancel)
    if cancel.is_set():
        raise Cancelled()
    if code != 0:
        raise ConvertError("unreadable", details)
    return total


def convert(src, dst=None, progress=lambda f: None, cancel=None):
    """Zamienia src na dst (domyślnie obok, .mp4). Zwraca długość filmu w sekundach.

    Zapis idzie do pliku tymczasowego – przerwana lub nieudana zamiana nie zostawia uszkodzonego MP4.
    """
    src = Path(src)
    dst = Path(dst) if dst else src.with_suffix(".mp4")
    cancel = cancel or threading.Event()
    tmp = dst.with_name(dst.name + ".tmp")
    try:
        if not src.exists():
            raise ConvertError("not_found")
        free = shutil.disk_usage(dst.parent).free
        if free < src.stat().st_size * 1.1:
            raise ConvertError("no_space")
        conv = _convert_jufen if is_jufen(src) else _convert_ffmpeg
        duration = conv(src, tmp, progress, cancel)
        os.replace(tmp, dst)
        st = src.stat()
        os.utime(dst, (st.st_atime, st.st_mtime))  # data filmu = data nagrania (sortowanie w folderze)
        progress(1.0)
        return duration
    except PermissionError as e:
        raise ConvertError("no_access", str(e))
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def collect(paths):
    """Pliki .dav z podanych plików i folderów (także podfolderów), bez powtórzeń."""
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".dav")
        elif p.is_file() and p.suffix.lower() == ".dav":
            files.append(p)
    return list(dict.fromkeys(files))


if __name__ == "__main__":
    files = collect(sys.argv[1:])
    if not files:
        sys.exit("Usage: python converter.py <file.dav | folder> [...]")
    ok = 0
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.name} ... ", end="", flush=True)
        dst = f.with_suffix(".mp4")
        if dst.exists() and dst.stat().st_size > 0:
            print("already converted")
            ok += 1
            continue
        try:
            d = convert(f, dst)
            print(f"OK ({int(d // 60)} min {int(d % 60)} s)")
            ok += 1
        except ConvertError as e:
            print(f"FAILED: {e.message('en')}\n    {e.details.splitlines()[-1] if e.details else ''}")
    print(f"Done: {ok}/{len(files)}")
    sys.exit(0 if ok == len(files) else 1)
