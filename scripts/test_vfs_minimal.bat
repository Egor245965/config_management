@echo off
python %~dp0\..\src\emulator.py --vfs %~dp0\..\vfs\minimal.zip
pause