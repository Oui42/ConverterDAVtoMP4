"""ConverterDAVtoMP4 – okno programu (duże, proste, dla mniej wprawnych użytkowników), PL/EN.

Filmy MP4 zapisują się obok nagrań DAV, z tą samą nazwą. Nagrania przeciągnięte na ikonę programu
zamieniają się od razu. Wybrany język jest zapamiętany w %APPDATA%\\ConverterDAVtoMP4\\settings.json
(program jest jednym plikiem .exe – obok niego nic nie zapisujemy).
"""
import json
import locale
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import converter

# kolory
BG = "#f4f6f9"
CARD = "#ffffff"
HEADER = "#1d4f91"
PRIMARY = "#1d6fd8"
PRIMARY_HOVER = "#1558b0"
TEXT = "#1c2430"
MUTED = "#5b6675"
GREEN = "#1f9d55"
RED = "#c62828"
BORDER = "#d9dee6"
FONT = "Segoe UI"

TEXTS = {
    "pl": {
        "app_name": "Konwerter nagrań z kamer",
        "header_sub": "Zamienia nagrania .dav z rejestratora na zwykłe filmy .mp4.\n"
                      "Otworzysz je na każdym komputerze i telefonie.",
        "question": "Co chcesz zamienić?",
        "btn_files": "Wybierz nagrania", "btn_files_sub": "jedno lub kilka nagrań",
        "btn_folder": "Wybierz folder", "btn_folder_sub": "wszystkie nagrania z folderu",
        "tip": "Gotowe filmy zapiszą się w tym samym folderze co nagrania, pod tą samą nazwą.\n"
               "Nagrania .dav zostają nietknięte.",
        "hint": "Wskazówka: nagrania można też po prostu przeciągnąć na ikonę programu.",
        "working": "Trwa zamiana nagrań…",
        "working_sub": "Można w tym czasie korzystać z komputera. Nie wyłączaj go do końca.",
        "file_n": "Nagranie {i} z {n}:  {name}",
        "all": "Wszystkie nagrania:",
        "eta": "Do końca zostało {t}",
        "less_minute": "mniej niż minuta",
        "col_name": "Nagranie", "col_status": "Stan",
        "st_wait": "Czeka", "st_run": "Trwa…", "st_run_pct": "Trwa…  {p}%",
        "st_ok": "Gotowe ✔  ({len})", "st_skip": "Był już zamieniony ✔", "st_err": "Nie udało się ✘",
        "st_cancel": "Przerwano", "st_skipped": "Pominięto",
        "btn_stop": "Zatrzymaj", "btn_open": "Otwórz folder z filmami", "btn_again": "Zamień kolejne nagrania",
        "done_ok": "Gotowe! Wszystkie nagrania zamienione ✔",
        "done_ok_sub": "Filmów: {n}. Są w tym samym folderze co nagrania.",
        "done_err": "Gotowe – nie wszystkie nagrania udało się zamienić",
        "done_err_sub": "Zamienione: {ok} z {n}. Nieudane są zaznaczone na czerwono.",
        "done_cancel": "Zamiana została zatrzymana",
        "done_cancel_sub": "Gotowe filmy: {n}. Aby dokończyć, wybierz nagrania jeszcze raz – "
                           "gotowe zostaną pominięte.",
        "stopping": "Zatrzymywanie…",
        "dlg_files": "Wybierz nagrania do zamiany", "filetype": "Nagrania z kamer (.dav)",
        "dlg_folder": "Wybierz folder z nagraniami",
        "no_files": "W tym folderze (ani w folderach w nim) nie ma nagrań .dav.\n\nWybierz inny folder.",
        "errors_list": "Tych nagrań nie udało się zamienić:",
        "errors_more": "…i {n} innych.",
        "ask_stop": "Czy na pewno zatrzymać zamianę?\n\nGotowe filmy zostaną zachowane.",
        "ask_close": "Zamiana jeszcze trwa.\n\nCzy na pewno zamknąć program? "
                     "Film, który jest teraz zamieniany, nie zostanie zapisany.",
    },
    "en": {
        "app_name": "Camera Recording Converter",
        "header_sub": "Turns .dav recordings from your video recorder into regular .mp4 videos.\n"
                      "They play on any computer and phone.",
        "question": "What would you like to convert?",
        "btn_files": "Choose recordings", "btn_files_sub": "one or more recordings",
        "btn_folder": "Choose a folder", "btn_folder_sub": "all recordings in a folder",
        "tip": "Finished videos are saved in the same folder as the recordings, with the same name.\n"
               "The .dav recordings are left untouched.",
        "hint": "Tip: you can also simply drag recordings onto the program icon.",
        "working": "Converting recordings…",
        "working_sub": "You can keep using the computer. Please don't turn it off until it's done.",
        "file_n": "Recording {i} of {n}:  {name}",
        "all": "All recordings:",
        "eta": "Time left: {t}",
        "less_minute": "less than a minute",
        "col_name": "Recording", "col_status": "Status",
        "st_wait": "Waiting", "st_run": "Working…", "st_run_pct": "Working…  {p}%",
        "st_ok": "Done ✔  ({len})", "st_skip": "Already converted ✔", "st_err": "Failed ✘",
        "st_cancel": "Stopped", "st_skipped": "Skipped",
        "btn_stop": "Stop", "btn_open": "Open folder with videos", "btn_again": "Convert more recordings",
        "done_ok": "Done! All recordings converted ✔",
        "done_ok_sub": "Videos: {n}. They are in the same folder as the recordings.",
        "done_err": "Done – some recordings could not be converted",
        "done_err_sub": "Converted: {ok} of {n}. Failed ones are marked in red.",
        "done_cancel": "Conversion stopped",
        "done_cancel_sub": "Finished videos: {n}. To finish, choose the recordings again – "
                           "finished ones will be skipped.",
        "stopping": "Stopping…",
        "dlg_files": "Choose recordings to convert", "filetype": "Camera recordings (.dav)",
        "dlg_folder": "Choose a folder with recordings",
        "no_files": "There are no .dav recordings in this folder (or its subfolders).\n\n"
                    "Please choose another folder.",
        "errors_list": "These recordings could not be converted:",
        "errors_more": "…and {n} more.",
        "ask_stop": "Stop converting?\n\nFinished videos will be kept.",
        "ask_close": "Conversion is still running.\n\nClose the program anyway? "
                     "The video being converted right now will not be saved.",
    },
}

SETTINGS = Path(os.environ.get("APPDATA") or Path.home()) / "ConverterDAVtoMP4" / "settings.json"


def resource(name):
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).parent
    return Path(base) / name


def load_lang():
    try:
        lang = json.loads(SETTINGS.read_text(encoding="utf-8")).get("lang")
        if lang in TEXTS:
            return lang
    except (OSError, ValueError):
        pass
    return system_lang()


def system_lang():
    """Polski, gdy Windows jest po polsku, w każdym innym przypadku angielski."""
    try:
        import ctypes
        code = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
    except (AttributeError, OSError):
        code = locale.getlocale()[0] or ""
    return "pl" if code.lower().startswith("pl") else "en"


def save_lang(lang):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps({"lang": lang}), encoding="utf-8")
    except OSError:
        pass  # brak zapisu nie może przeszkadzać w pracy


def minutes_text(lang, seconds):
    if seconds < 60:
        return TEXTS[lang]["less_minute"]
    m = round(seconds / 60)
    if lang == "en":
        return f"about {m} minute{'s' if m != 1 else ''}"
    if m == 1:
        word = "minuta"
    elif 2 <= m % 10 <= 4 and not 12 <= m % 100 <= 14:
        word = "minuty"
    else:
        word = "minut"
    return f"około {m} {word}"


def length_text(lang, seconds):
    m = int(seconds // 60)
    hours = "godz." if lang == "pl" else "h"
    if m >= 60:
        return f"{m // 60} {hours} {m % 60} min"
    return f"{m} min" if m else f"{int(seconds)} s"


class BigButton(tk.Frame):
    """Duży przycisk z tytułem i podpisem, podświetlany pod myszą."""

    def __init__(self, parent, command, primary=True, subtitle=True):
        self.bg, self.hover = (PRIMARY, PRIMARY_HOVER) if primary else (CARD, "#e9eef6")
        fg, sub_fg = ("white", "#dbe8fb") if primary else (TEXT, MUTED)
        super().__init__(parent, bg=self.bg, cursor="hand2", highlightthickness=0 if primary else 1,
                         highlightbackground=BORDER)
        self.command = command
        self.title = tk.Label(self, font=(FONT, 16, "bold"), bg=self.bg, fg=fg)
        self.title.pack(padx=28, pady=(18, 2 if subtitle else 18))
        self.labels = [self.title]
        self.sub = None
        if subtitle:
            self.sub = tk.Label(self, font=(FONT, 11), bg=self.bg, fg=sub_fg)
            self.sub.pack(padx=28, pady=(0, 18))
            self.labels.append(self.sub)
        for w in [self, *self.labels]:
            w.bind("<Enter>", lambda e: self._paint(self.hover))
            w.bind("<Leave>", lambda e: self._paint(self.bg))
            w.bind("<Button-1>", lambda e: self.command())

    def set_text(self, title, subtitle=None):
        self.title.config(text=title)
        if self.sub is not None:
            self.sub.config(text=subtitle or "")

    def _paint(self, color):
        for w in [self, *self.labels]:
            w.config(bg=color)


class FlagButton(tk.Canvas):
    """Flaga do wyboru języka (rysowana – Windows nie wyświetla flag z emoji)."""

    def __init__(self, parent, kind, scale, command):
        stripe = max(3, round(3 * scale))
        h = 13 * stripe
        w = round(h * 1.6)
        pad = max(3, round(3 * scale))
        super().__init__(parent, width=w + 2 * pad, height=h + 2 * pad, bg=HEADER, highlightthickness=0,
                         cursor="hand2")
        self.pad, self.w, self.h = pad, w, h
        x0, y0 = pad, pad
        if kind == "pl":
            self.create_rectangle(x0, y0, x0 + w, y0 + h / 2, fill="white", width=0)
            self.create_rectangle(x0, y0 + h / 2, x0 + w, y0 + h, fill="#dc143c", width=0)
        else:  # USA: 13 pasów, niebieski kanton z gwiazdkami (kropki)
            for i in range(13):
                self.create_rectangle(x0, y0 + i * stripe, x0 + w, y0 + (i + 1) * stripe,
                                      fill="#b22234" if i % 2 == 0 else "white", width=0)
            cw, ch = round(w * 0.4), 7 * stripe
            self.create_rectangle(x0, y0, x0 + cw, y0 + ch, fill="#3c3b6e", width=0)
            r = max(0.6, 0.5 * scale)
            for row in range(4):
                for col in range(5):
                    cx = x0 + cw * (col + 0.5) / 5
                    cy = y0 + ch * (row + 0.5) / 4
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, fill="white", width=0)
        self.ring = self.create_rectangle(1, 1, w + 2 * pad - 1, h + 2 * pad - 1, outline="", width=2)
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self.selected or self.itemconfig(self.ring, outline="#8fb3e6"))
        self.bind("<Leave>", lambda e: self.selected or self.itemconfig(self.ring, outline=""))
        self.selected = False

    def select(self, on):
        self.selected = on
        self.itemconfig(self.ring, outline="white" if on else "")


class App:
    def __init__(self, root, initial_paths):
        self.root = root
        self.lang = load_lang()
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.outputs = []
        self.files = []
        self.rows = []
        self.row_state = []          # (klucz, argumenty, tag) dla każdego wiersza listy
        self.title_state = ("working", {}, TEXT)
        self.subtitle_state = ("working_sub", {})
        self.current = None
        self.eta_seconds = None

        root.configure(bg=BG)
        root.minsize(760, 600)
        try:
            root.iconbitmap(default=str(resource("app.ico")))
        except tk.TclError:
            pass
        self._center(820, 660)
        self._styles()

        header = tk.Frame(root, bg=HEADER)
        header.pack(fill="x")
        top = tk.Frame(header, bg=HEADER)
        top.pack(fill="x", padx=(28, 20), pady=(20, 0))
        self.h_title = tk.Label(top, font=(FONT, 22, "bold"), bg=HEADER, fg="white")
        self.h_title.pack(side="left")
        flags = tk.Frame(top, bg=HEADER)
        flags.pack(side="right", anchor="n")
        scale = root.winfo_fpixels("1i") / 96
        self.flags = {}
        for code in ("en", "pl"):
            f = FlagButton(flags, "us" if code == "en" else "pl", scale, lambda c=code: self.set_lang(c))
            f.pack(side="left", padx=(6, 0))
            self.flags[code] = f
        self.h_sub = tk.Label(header, font=(FONT, 12), bg=HEADER, fg="#cfe0f7", justify="left")
        self.h_sub.pack(anchor="w", padx=28, pady=(4, 20))

        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=28, pady=24)
        self._build_start()
        self._build_work()
        self.show_start()
        self.refresh_texts()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self._poll)
        if initial_paths:
            root.after(300, lambda: self.start(converter.collect(initial_paths)))

    def t(self, key, **kw):
        return TEXTS[self.lang][key].format(**kw)

    # --- wygląd ---------------------------------------------------------------------------

    def _center(self, w, h):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max((sh - h) // 2 - 20, 0)}")

    def _styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("File.Horizontal.TProgressbar", thickness=26, troughcolor="#e3e8ef", background=PRIMARY,
                    bordercolor="#e3e8ef", lightcolor=PRIMARY, darkcolor=PRIMARY)
        s.configure("All.Horizontal.TProgressbar", thickness=14, troughcolor="#e3e8ef", background=GREEN,
                    bordercolor="#e3e8ef", lightcolor=GREEN, darkcolor=GREEN)
        s.configure("Files.Treeview", font=(FONT, 12), rowheight=34, background=CARD, fieldbackground=CARD,
                    bordercolor=BORDER, foreground=TEXT)
        s.configure("Files.Treeview.Heading", font=(FONT, 11, "bold"), background="#e9eef6",
                    foreground=MUTED, relief="flat")
        s.map("Files.Treeview", background=[("selected", "#dbe8fb")], foreground=[("selected", TEXT)])

    def _build_start(self):
        f = self.start_frame = tk.Frame(self.body, bg=BG)
        self.l_question = tk.Label(f, font=(FONT, 18, "bold"), bg=BG, fg=TEXT)
        self.l_question.pack(anchor="w", pady=(10, 18))
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x")
        self.btn_files = BigButton(row, self.pick_files)
        self.btn_files.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.btn_folder = BigButton(row, self.pick_folder)
        self.btn_folder.pack(side="left", fill="x", expand=True, padx=(10, 0))

        tip = tk.Frame(f, bg="#e8f1fc", highlightthickness=1, highlightbackground="#c9dcf5")
        tip.pack(fill="x", pady=(28, 0))
        self.l_tip = tk.Label(tip, font=(FONT, 12), bg="#e8f1fc", fg=TEXT, justify="left")
        self.l_tip.pack(anchor="w", padx=18, pady=14)
        self.l_hint = tk.Label(f, font=(FONT, 11), bg=BG, fg=MUTED)
        self.l_hint.pack(anchor="w", pady=(14, 0))

    def _build_work(self):
        f = self.work_frame = tk.Frame(self.body, bg=BG)

        self.title = tk.Label(f, font=(FONT, 18, "bold"), bg=BG, fg=TEXT, anchor="w")
        self.title.pack(fill="x")
        self.subtitle = tk.Label(f, font=(FONT, 12), bg=BG, fg=MUTED, anchor="w", justify="left",
                                 wraplength=740)
        self.subtitle.pack(fill="x", pady=(2, 12))

        self.progress_box = tk.Frame(f, bg=BG)
        self.progress_box.pack(fill="x")
        line = tk.Frame(self.progress_box, bg=BG)
        line.pack(fill="x")
        self.file_label = tk.Label(line, font=(FONT, 12, "bold"), bg=BG, fg=TEXT, anchor="w")
        self.file_label.pack(side="left", fill="x", expand=True)
        self.percent = tk.Label(line, font=(FONT, 16, "bold"), bg=BG, fg=PRIMARY)
        self.percent.pack(side="right")
        self.file_bar = ttk.Progressbar(self.progress_box, style="File.Horizontal.TProgressbar", maximum=1000)
        self.file_bar.pack(fill="x", pady=(4, 12))
        line2 = tk.Frame(self.progress_box, bg=BG)
        line2.pack(fill="x")
        self.l_all = tk.Label(line2, font=(FONT, 11), bg=BG, fg=MUTED)
        self.l_all.pack(side="left")
        self.eta = tk.Label(line2, font=(FONT, 11), bg=BG, fg=MUTED)
        self.eta.pack(side="right")
        self.all_bar = ttk.Progressbar(self.progress_box, style="All.Horizontal.TProgressbar", maximum=1000)
        self.all_bar.pack(fill="x", pady=(4, 14))

        # przyciski przypięte do dołu – lista nie może ich wypchnąć poza okno
        self.buttons = tk.Frame(f, bg=BG)
        self.buttons.pack(side="bottom", fill="x", pady=(16, 0))
        self.btn_stop = BigButton(self.buttons, self.stop, primary=False, subtitle=False)
        self.btn_open = BigButton(self.buttons, self.open_folder, subtitle=False)
        self.btn_again = BigButton(self.buttons, self.show_start, primary=False, subtitle=False)

        box = tk.Frame(f, bg=BORDER)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, columns=("status",), style="Files.Treeview", selectmode="none")
        self.tree.column("#0", width=420, anchor="w")
        self.tree.column("status", width=250, anchor="w")
        for tag, color in (("wait", MUTED), ("run", PRIMARY), ("ok", GREEN), ("err", RED)):
            self.tree.tag_configure(tag, foreground=color)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sb.pack(side="right", fill="y")

    def show_start(self):
        self.work_frame.pack_forget()
        self.start_frame.pack(fill="both", expand=True)

    def _show_work(self):
        self.start_frame.pack_forget()
        self.work_frame.pack(fill="both", expand=True)

    # --- język ----------------------------------------------------------------------------

    def set_lang(self, lang):
        if lang != self.lang:
            self.lang = lang
            save_lang(lang)
            self.refresh_texts()

    def refresh_texts(self):
        t = self.t
        for code, flag in self.flags.items():
            flag.select(code == self.lang)
        self.root.title(t("app_name"))
        self.h_title.config(text=t("app_name"))
        self.h_sub.config(text=t("header_sub"))
        self.l_question.config(text=t("question"))
        self.btn_files.set_text(t("btn_files"), t("btn_files_sub"))
        self.btn_folder.set_text(t("btn_folder"), t("btn_folder_sub"))
        self.l_tip.config(text=t("tip"))
        self.l_hint.config(text=t("hint"))
        self.l_all.config(text=t("all"))
        self.btn_stop.set_text(t("btn_stop"))
        self.btn_open.set_text(t("btn_open"))
        self.btn_again.set_text(t("btn_again"))
        self.tree.heading("#0", text="  " + t("col_name"), anchor="w")
        self.tree.heading("status", text=t("col_status"), anchor="w")
        key, kw, color = self.title_state
        self.title.config(text=t(key, **kw), fg=color)
        key, kw = self.subtitle_state
        self.subtitle.config(text=t(key, **kw))
        if self.current is not None:
            self.file_label.config(text=t("file_n", i=self.current + 1, n=len(self.files),
                                          name=self.files[self.current].name))
        self._show_eta()
        for i in range(len(self.rows)):
            self._render_row(i)

    def _set_title(self, key, color=TEXT, **kw):
        self.title_state = (key, kw, color)
        self.title.config(text=self.t(key, **kw), fg=color)

    def _set_subtitle(self, key, **kw):
        self.subtitle_state = (key, kw)
        self.subtitle.config(text=self.t(key, **kw))

    def _show_eta(self):
        self.eta.config(text=self.t("eta", t=minutes_text(self.lang, self.eta_seconds))
                        if self.eta_seconds is not None else "")

    # --- wybór plików ---------------------------------------------------------------------

    def pick_files(self):
        paths = filedialog.askopenfilenames(parent=self.root, title=self.t("dlg_files"),
                                            filetypes=[(self.t("filetype"), "*.dav *.DAV")])
        if paths:
            self.start(converter.collect(paths))

    def pick_folder(self):
        d = filedialog.askdirectory(parent=self.root, title=self.t("dlg_folder"))
        if not d:
            return
        files = converter.collect([d])
        if not files:
            messagebox.showinfo(self.t("app_name"), self.t("no_files"), parent=self.root)
            return
        self.start(files)

    # --- praca ----------------------------------------------------------------------------

    def start(self, files):
        if not files or self.worker:
            return
        self.files = files
        self.outputs = []
        self.cancel.clear()
        self.tree.delete(*self.tree.get_children())
        self.rows = [self.tree.insert("", "end", text="  " + p.name) for p in files]
        self.row_state = [("st_wait", {}, "wait") for _ in files]
        for i in range(len(files)):
            self._render_row(i)
        self.current = None
        self.eta_seconds = None
        self._set_title("working")
        self._set_subtitle("working_sub")
        self.progress_box.pack(fill="x", before=self.tree.master)
        self.file_bar["value"] = self.all_bar["value"] = 0
        self.percent.config(text="0%")
        self.file_label.config(text="")
        self._show_eta()
        for b in (self.btn_open, self.btn_again):
            b.pack_forget()
        self.btn_stop.pack(side="left")
        self._show_work()

        self.sizes = [p.stat().st_size if p.exists() else 0 for p in files]
        self.total_bytes = sum(self.sizes) or 1
        self.started = time.monotonic()
        self.worker = threading.Thread(target=self._work, daemon=True)
        self.worker.start()

    def _work(self):
        results = []
        for i, src in enumerate(self.files):
            if self.cancel.is_set():
                results.append(("cancel", None))
                self.events.put(("status", i, "st_skipped", {}, "wait"))
                continue
            dst = src.with_suffix(".mp4")
            if dst.exists() and dst.stat().st_size > 0:
                results.append(("skip", dst))
                self.events.put(("status", i, "st_skip", {}, "ok"))
                self.events.put(("progress", i, 1.0))
                continue
            self.events.put(("begin", i))
            try:
                dur = converter.convert(src, dst, lambda fr, i=i: self.events.put(("progress", i, fr)),
                                        self.cancel)
                results.append(("ok", dst))
                self.events.put(("status", i, "st_ok", {"dur": dur}, "ok"))
            except converter.Cancelled:
                results.append(("cancel", None))
                self.events.put(("status", i, "st_cancel", {}, "err"))
            except converter.ConvertError as e:
                results.append(("err", (src, e)))
                self.events.put(("status", i, "st_err", {}, "err"))
            except Exception as e:  # nieoczekiwany błąd – nie może zatrzymać pozostałych plików
                results.append(("err", (src, converter.ConvertError("unexpected", repr(e)))))
                self.events.put(("status", i, "st_err", {}, "err"))
        self.events.put(("done", results))

    def _poll(self):
        last_progress = None
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "begin":
                    i = self.current = ev[1]
                    self.file_label.config(text=self.t("file_n", i=i + 1, n=len(self.files),
                                                       name=self.files[i].name))
                    self._set_row(i, "st_run", {}, "run")
                    self.tree.see(self.rows[i])
                elif kind == "progress":
                    last_progress = ev[1:]
                elif kind == "status":
                    self._set_row(*ev[1:])
                elif kind == "done":
                    self._finish(ev[1])
        except queue.Empty:
            pass
        if last_progress and self.worker:
            self._show_progress(*last_progress)
        self.root.after(100, self._poll)

    def _set_row(self, i, key, kw, tag):
        self.row_state[i] = (key, kw, tag)
        self._render_row(i)

    def _render_row(self, i):
        key, kw, tag = self.row_state[i]
        if "dur" in kw:
            kw = {"len": length_text(self.lang, kw["dur"])}
        self.tree.item(self.rows[i], values=(self.t(key, **kw),), tags=(tag,))

    def _show_progress(self, i, frac):
        frac = max(0.0, min(frac, 1.0))
        self.file_bar["value"] = frac * 1000
        self.percent.config(text=f"{int(frac * 100)}%")
        if frac < 1 and self.row_state[i][0] in ("st_run", "st_run_pct"):
            self._set_row(i, "st_run_pct", {"p": int(frac * 100)}, "run")
        done = sum(self.sizes[:i]) + self.sizes[i] * frac
        total = done / self.total_bytes
        self.all_bar["value"] = total * 1000
        elapsed = time.monotonic() - self.started
        if total > 0.02 and elapsed > 3:
            self.eta_seconds = elapsed / total * (1 - total)
            self._show_eta()

    def _finish(self, results):
        self.worker = None
        self.current = None
        ok = [r for k, r in results if k in ("ok", "skip")]
        errors = [r for k, r in results if k == "err"]
        cancelled = any(k == "cancel" for k, _ in results)
        self.outputs = ok
        self.btn_stop.pack_forget()
        self.progress_box.pack_forget()
        if ok:
            self.btn_open.pack(side="left", padx=(0, 12))
        self.btn_again.pack(side="left")

        if cancelled:
            self._set_title("done_cancel")
            self._set_subtitle("done_cancel_sub", n=len(ok))
        elif errors:
            self._set_title("done_err", RED)
            self._set_subtitle("done_err_sub", ok=len(ok), n=len(results))
        else:
            self._set_title("done_ok", GREEN)
            self._set_subtitle("done_ok_sub", n=len(ok))
        self.root.bell()
        if errors:
            msg = "\n\n".join(f"• {src.name}\n   {e.message(self.lang)}" for src, e in errors[:8])
            if len(errors) > 8:
                msg += "\n\n" + self.t("errors_more", n=len(errors) - 8)
            messagebox.showwarning(self.t("app_name"), self.t("errors_list") + "\n\n" + msg, parent=self.root)

    def stop(self):
        if self.worker and messagebox.askyesno(self.t("app_name"), self.t("ask_stop"), parent=self.root):
            self.cancel.set()
            self._set_title("stopping")

    def open_folder(self):
        if not self.outputs:
            return
        target = self.outputs[0]
        if target.exists():
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            os.startfile(target.parent)

    def on_close(self):
        if self.worker:
            if not messagebox.askyesno(self.t("app_name"), self.t("ask_close"), parent=self.root):
                return
            self.cancel.set()
            self.worker.join(timeout=5)
        self.root.destroy()


def main():
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # ostre napisy na ekranach ze skalowaniem
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ConverterDAVtoMP4")
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    App(root, sys.argv[1:])
    try:  # ekran „Uruchamianie…” z wersji jednoplikowej (PyInstaller --splash)
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
