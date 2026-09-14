@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 -m venv .venv
if errorlevel 1 goto failed
goto install
:use_python
where python >nul 2>&1
if errorlevel 1 goto missing
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
if not defined NCS_PORT set "NCS_PORT=5000"
echo.
echo Open http://127.0.0.1:%NCS_PORT% in your browser.
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
goto end
:missing
echo Python not found. Install Python 3.11 or newer and enable Add python.exe to PATH.
echo Then run this file again.
pause
goto end
:failed
echo.
echo Startup failed. Please read the error above and README.md.
pause
:end
endlocal
