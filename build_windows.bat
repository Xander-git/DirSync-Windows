@echo off
REM Build script for DirSync-Windows executable
REM Requires Python 3.11+ and PyInstaller

echo Building DirSync-Windows...
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.11 or higher
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

REM Build executable
echo.
echo Building executable with PyInstaller...
pyinstaller app.py ^
  --name DirSync-Windows ^
  --onefile ^
  --noconsole ^
  --uac-admin ^
  --icon=assets/SnP-ImagerSyncIcon.png ^
  --add-data "assets;assets" ^
  --clean

if %errorlevel% equ 0 (
    echo.
    echo Build successful!
    echo Executable: dist\DirSync-Windows.exe
    echo.
) else (
    echo.
    echo Build failed with error code %errorlevel%
    echo.
    pause
    exit /b %errorlevel%
)

pause

