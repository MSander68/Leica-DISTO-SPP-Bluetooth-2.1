Build a single EXE (PyInstaller + UPX)
pip install pyinstaller
pyinstaller --onefile --noconsole --name DISTO-D8-Remote disto_d8_gui_R3.py
# Optional: compress with UPX 5.x (download separately)
upx --best --lzma dist/DISTO-D8-Remote.exe


If PyInstaller warns about a missing api-ms-*.dll, install the latest VC++ runtime or use --add-binary as needed.