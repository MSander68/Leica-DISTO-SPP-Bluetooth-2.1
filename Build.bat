@echo off
REM ===============================
REM GUI (Slim EXE with UPX)
REM ===============================

REM Change to script directory
cd /d "%~dp0"

REM Clean any old build/dist folders
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM Run PyInstaller
pyinstaller --onefile --noconsole --clean --upx-dir "C:\Python\upx-5.0.2" disto_d8_guiR3.py

echo.
echo Build complete. EXE is in the 'dist' folder.
pause
