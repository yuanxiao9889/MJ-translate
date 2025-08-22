@echo off
chcp 65001 >nul
title MJ Translator - Environment Setup
echo ========================================
echo MJ Translator Environment Setup
echo ========================================
echo.

REM Check if Python is installed
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found! Please install Python first.
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found successfully.
echo.

REM Create virtual environment if it doesn't exist
if exist "venv" (
    echo Virtual environment already exists.
) else (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)
echo Virtual environment activated.
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo Installing dependencies from requirements.txt...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Warning: Some packages failed to install.
        echo Please check the error messages above.
    ) else (
        echo All dependencies installed successfully.
    )
) else (
    echo Warning: requirements.txt not found.
    echo Installing basic dependencies...
    pip install customtkinter Pillow requests pyperclip tkcalendar pystray oss2 semver chardet
)
echo.

REM Test installation
echo Testing installation...
python -c "import customtkinter, PIL, requests, pyperclip, tkcalendar, pystray, oss2, semver, chardet; print('All modules imported successfully!')" 2>nul
if errorlevel 1 (
    echo Warning: Some modules failed to import. Please check the installation.
) else (
    echo Installation test passed!
)
echo.

echo ========================================
echo Setup completed!
echo ========================================
echo You can now run the application using start.bat
echo.
pause