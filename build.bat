@echo off
rem Builds dist\ConverterDAVtoMP4.exe - one portable file (program + ffmpeg, no Python needed)
rem and a "ConverterDAVtoMP4" shortcut on the desktop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv || (echo Python not found. & pause & exit /b 1)
)
.venv\Scripts\python -m pip install -q imageio-ffmpeg pyinstaller || (pause & exit /b 1)
for /f "delims=" %%f in ('.venv\Scripts\python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"') do copy /y "%%f" ffmpeg.exe >nul
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --onefile --name ConverterDAVtoMP4 ^
  --icon "%~dp0app.ico" --splash "%~dp0splash.png" --add-data "%~dp0app.ico;." --add-binary "%~dp0ffmpeg.exe;." ^
  --exclude-module imageio_ffmpeg --exclude-module PIL ^
  --workpath "%TEMP%\pyi-build" --specpath "%TEMP%\pyi-build" "%~dp0app.py" || (pause & exit /b 1)
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\ConverterDAVtoMP4.lnk'); $s.TargetPath='%~dp0dist\ConverterDAVtoMP4.exe'; $s.WorkingDirectory='%~dp0dist'; $s.IconLocation='%~dp0dist\ConverterDAVtoMP4.exe,0'; $s.Save()"
echo Done: dist\ConverterDAVtoMP4.exe
pause
