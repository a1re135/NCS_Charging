@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo NCS Charging - DEV + LIM merge v2
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 merge_dev_lim_v2.py
) else (
  python merge_dev_lim_v2.py
)
echo.
echo Press any key to close.
pause >nul
