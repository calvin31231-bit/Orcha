@echo off
echo ============================================================
echo  Mordu Market Engine - Windows Installer Build Script
echo ============================================================
echo.

echo [1/4] Installing Python dependencies...
cd python_core
pip install pyinstaller ollama aiohttp fastapi uvicorn pyjwt aiosqlite

echo.
echo [2/4] Freezing Python server with PyInstaller...
pyinstaller --onefile --name mordu_server ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.lifespan.on ^
    --collect-all ollama ^
    mordu_server.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo [3/4] Deploying server executable to Tauri...
cd ..
if not exist "src-tauri\bin" mkdir "src-tauri\bin"
move /Y "python_core\dist\mordu_server.exe" "src-tauri\bin\mordu_server-x86_64-pc-windows-msvc.exe"

if errorlevel 1 (
    echo ERROR: Failed to move executable!
    pause
    exit /b 1
)

echo.
echo [4/4] Building Tauri application...
npm install
npm run tauri build

if errorlevel 1 (
    echo ERROR: Tauri build failed! Ensure Rust and C++ Build Tools are installed.
    echo Download: https://www.rust-lang.org/tools/install
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE!
echo  Installer location: src-tauri\target\release\bundle\nsis\
echo ============================================================
pause
