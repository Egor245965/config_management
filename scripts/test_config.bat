@echo off
python  %~dp0\..\src\emulator.py --vfs vfs.zip --script startup.txt
pause