@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Virtual environment not found. Run setup_windows.ps1 first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
streamlit run dashboard.py
