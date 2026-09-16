@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo NCS Charging - LIM MySQL schema compatibility fix
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 fix_lim_mysql_schema.py
) else (
  python fix_lim_mysql_schema.py
)

echo.
pause
