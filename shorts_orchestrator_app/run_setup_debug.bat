@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  Shorts Orchestrator - Debug Setup Launcher
echo ============================================================
echo This window will stay open after setup so errors are visible.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
echo.
echo setup_windows.ps1 has finished or failed.
echo Check setup_log.txt in this folder for the full log.
pause
