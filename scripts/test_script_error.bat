@echo off
setlocal
cd /d "%~dp0.."
python src\emulator.py --vfs vfs\files.zip --script nonexistent.txt
