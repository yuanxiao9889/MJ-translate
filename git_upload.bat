@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo =================================
echo     GitHub Upload Script
echo =================================
echo.

REM Check if PowerShell is available
powershell -Command "Get-Host" >nul 2>&1
if errorlevel 1 (
    echo Error: PowerShell not found
    echo Please ensure Windows PowerShell is installed
    echo.
    pause
    exit /b 1
)

echo Executing PowerShell script...
echo.

REM Execute PowerShell script and keep window open
powershell -ExecutionPolicy Bypass -NoExit -File "%~dp0git_upload.ps1"

REM If PowerShell exits normally, show completion message
echo.
echo Operation completed, press any key to exit...
pause >nul