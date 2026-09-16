@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First launch: installing SoundShredder. This may take several minutes.
    python setup_runtime.py --device auto
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import bandit_infer, fastapi, torch, soundfile, scipy, imageio_ffmpeg, multipart" >nul 2>&1
if errorlevel 1 (
    python setup_runtime.py --device auto
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo SoundShredder could not start. Install Python 3.12 from python.org and enable Add Python to PATH.
echo You can also try Setup CPU.bat or Setup NVIDIA GPU.bat, then launch again.
pause
exit /b 1

