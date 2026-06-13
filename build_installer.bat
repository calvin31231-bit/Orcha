@echo off
setlocal enabledelayedexpansion

:: Anchor to this script's own directory so the build works no matter
:: where it is launched from (double-click, parent folder, PowerShell, etc.)
cd /d "%~dp0"

echo ============================================================
echo  Mordu Market Engine - Windows Installer Build Script
echo  Working dir: %CD%
echo ============================================================
echo.

:: Sanity check: make sure we are at the repo root
if not exist "python_core\mordu_server.py" (
    echo ERROR: Could not find python_core\mordu_server.py
    echo This script must live in the repo root next to the python_core folder.
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: --- Step 1: Install Python dependencies and freeze server -------------------
echo [1/4] Installing Python dependencies...
pushd python_core
pip install pyinstaller ollama aiohttp fastapi uvicorn pyjwt aiosqlite
if errorlevel 1 (
    echo ERROR: pip install failed! Is Python on your PATH?
    popd
    pause
    exit /b 1
)

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
    popd
    pause
    exit /b 1
)
popd

:: --- Step 2: Move executable to Tauri bin folder ----------------------------
echo.
echo [3/4] Deploying server executable to Tauri...
if not exist "src-tauri\bin" mkdir "src-tauri\bin"
move /Y "python_core\dist\mordu_server.exe" "src-tauri\bin\mordu_server-x86_64-pc-windows-msvc.exe"

if errorlevel 1 (
    echo ERROR: Failed to move executable!
    pause
    exit /b 1
)

:: --- Step 3: Build Tauri application ----------------------------------------
echo.
echo [4/4] Building Tauri application...
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed!
    pause
    exit /b 1
)
call npm run tauri build

if errorlevel 1 (
    echo ERROR: Tauri build failed! Ensure Rust and C++ Build Tools are installed.
    echo Download: https://www.rust-lang.org/tools/install
    echo Download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE!
echo  Installer location: src-tauri\target\release\bundle\nsis\
echo ============================================================
pause
endlocal
