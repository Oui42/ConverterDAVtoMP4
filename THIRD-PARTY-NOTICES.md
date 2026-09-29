# Third-party notices

The source code in this repository is released under the [MIT License](LICENSE).
The portable `ConverterDAVtoMP4.exe` from the Releases page also contains the following third-party software.

## FFmpeg

- The executable bundles an unmodified `ffmpeg.exe` (FFmpeg 7.1, "essentials" build by gyan.dev,
  distributed with the [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) Python package).
- ConverterDAVtoMP4 runs it as a separate program; it is not linked into the converter's code.
- This FFmpeg build is licensed under the **GNU General Public License version 3** –
  see [licenses/FFmpeg-GPL-3.0.txt](licenses/FFmpeg-GPL-3.0.txt).
- FFmpeg is a trademark of Fabrice Bellard, originator of the FFmpeg project.
- Source code:
  - FFmpeg 7.1: <https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz> (project page: <https://ffmpeg.org>)
  - build scripts and sources of the libraries used in this build: <https://www.gyan.dev/ffmpeg/builds/>

If you need the exact sources and cannot get them from the links above, open an issue in this repository.

## Python and the Python standard library (incl. Tkinter, Tcl/Tk)

- Python 3.12 – [Python Software Foundation License](https://docs.python.org/3/license.html)
- Tcl/Tk – [Tcl/Tk license](https://www.tcl.tk/software/tcltk/license.html) (BSD-style)

## PyInstaller

The executable is packaged with [PyInstaller](https://pyinstaller.org). Its bootloader is licensed under
the GPL version 2 or later **with a special exception** that allows distributing programs built with it
under any license.
