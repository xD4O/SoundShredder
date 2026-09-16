@echo off
setlocal
cd /d "%~dp0"
python setup_runtime.py --device cuda
pause

