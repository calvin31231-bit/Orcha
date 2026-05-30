@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m shorts_orchestrator.cli daily-batch --account ai_oddly_satisfying --query "cozy impossible machine" --query "tiny satisfying factory" --query "soft kinetic sculpture" --no-youtube --generate --provider mock --voice-provider mock
pause
