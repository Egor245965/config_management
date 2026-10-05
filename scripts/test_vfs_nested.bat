@echo off
python  %~dp0\..\src\emulator.py --vfs vfs\nested.zip --script startup.txt
pause