@echo off
setlocal
cd /d "%~dp0.."
python src\emulator.py --vfs vfs\nested.zip --script startup.txt
