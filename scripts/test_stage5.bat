@echo off
setlocal
cd /d "%~dp0.."
python scripts\build_demo_vfs.py
if errorlevel 1 exit /b 1
python src\emulator.py --vfs vfs\demo.zip --script scripts\stage5.txt
