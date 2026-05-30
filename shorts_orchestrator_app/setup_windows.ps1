Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$LogPath = Join-Path $PSScriptRoot "setup_log.txt"
Start-Transcript -Path $LogPath -Append | Out-Null

function Pause-Setup {
    Write-Host ""
    Write-Host "Setup window is staying open so you can read the result." -ForegroundColor Cyan
    Write-Host "A full log was written to: $LogPath" -ForegroundColor Cyan
    Write-Host "Press Enter to close this window..." -ForegroundColor Yellow
    [void][System.Console]::ReadLine()
}

try {
    Set-Location $PSScriptRoot
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Shorts Orchestrator - Windows Setup" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Working folder: $PSScriptRoot"
    Write-Host "Log file: $LogPath"
    Write-Host ""

    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $PythonExe = "py"
        $PythonArgs = @("-3")
    } else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python was not found. Install Python 3.11 or 3.12 from python.org, then rerun setup. Make sure 'Add Python to PATH' is checked during install."
        }
        $PythonExe = "python"
        $PythonArgs = @()
    }

    Write-Host "Checking Python..." -ForegroundColor Green
    & $PythonExe @PythonArgs --version
    if ($LASTEXITCODE -ne 0) { throw "Python check failed." }

    if (-not (Test-Path ".venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Green
        & $PythonExe @PythonArgs -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
    } else {
        Write-Host "Virtual environment already exists. Reusing .venv" -ForegroundColor DarkGray
    }

    $VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python was not found at $VenvPython"
    }

    Write-Host "Upgrading pip..." -ForegroundColor Green
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

    Write-Host "Installing requirements..." -ForegroundColor Green
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Failed to install requirements. Check setup_log.txt for the package that failed." }

    if (!(Test-Path ".env")) {
        Copy-Item .env.example .env
        Write-Host "Created .env from .env.example" -ForegroundColor Green
    } else {
        Write-Host ".env already exists. Leaving it unchanged." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "Setup complete." -ForegroundColor Green
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Install Ollama if you have not already."
    Write-Host "  2. Run: ollama pull qwen2.5:7b"
    Write-Host "  3. Run: ollama pull llama3.1:8b"
    Write-Host "  4. Launch HUD with: launch_dashboard.bat"
}
catch {
    Write-Host ""
    Write-Host "SETUP FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Most common fixes:" -ForegroundColor Yellow
    Write-Host "  - Install Python 3.11 or 3.12 and check 'Add Python to PATH'."
    Write-Host "  - Run this from the unzipped folder, not inside the ZIP preview."
    Write-Host "  - Right-click the folder > Properties > Unblock, if Windows blocked downloaded scripts."
    Write-Host "  - Try running run_setup_debug.bat instead of double-clicking the .ps1 file."
    Write-Host ""
}
finally {
    Stop-Transcript | Out-Null
    Pause-Setup
}
