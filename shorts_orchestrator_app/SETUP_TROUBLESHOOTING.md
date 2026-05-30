# Setup troubleshooting

If `setup_windows.ps1` flashes open and instantly closes, do not double-click the PowerShell file directly.

Use one of these instead:

## Option 1: Run the debug launcher

Double-click:

```text
run_setup_debug.bat
```

This keeps the window open and writes a full log to:

```text
setup_log.txt
```

## Option 2: Run from PowerShell manually

Open PowerShell, then run:

```powershell
cd "C:\path\to\shorts_orchestrator_app"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

## Common causes

- Python is not installed.
- Python is installed but not added to PATH.
- The project is still inside the ZIP preview and has not been extracted.
- Windows blocked the downloaded files.
- A Python package failed to install.

For Python, install Python 3.11 or 3.12 from python.org and check **Add Python to PATH** during installation.
