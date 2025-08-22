@echo off
chcp 65001 >nul
title MJ Translator - AI翻译工具
echo Starting MJ Translator...
echo.

REM Check and activate virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Found local virtual environment, activating...
    call venv\Scripts\activate.bat
    if errorlevel 1 (
        echo Warning: Failed to activate virtual environment, using system Python
    ) else (
        echo Virtual environment activated successfully
    )
) else (
    echo No local virtual environment found, using system Python
    echo To create virtual environment, run: python -m venv venv
)
echo.

REM Check if Python is available
echo Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not detected, please install Python first
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check and install dependencies
echo Checking dependencies...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing tkinter...
    python -m pip install tk
)

python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing customtkinter...
    python -m pip install customtkinter
)

python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing Pillow...
    python -m pip install Pillow
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo Installing requests...
    python -m pip install requests
)

python -c "import pyperclip" >nul 2>&1
if errorlevel 1 (
    echo Installing pyperclip...
    python -m pip install pyperclip
)

python -c "import tkcalendar" >nul 2>&1
if errorlevel 1 (
    echo Installing tkcalendar...
    python -m pip install tkcalendar
)

python -c "import pystray" >nul 2>&1
if errorlevel 1 (
    echo Installing pystray...
    python -m pip install pystray
)

python -c "import oss2" >nul 2>&1
if errorlevel 1 (
    echo Installing oss2...
    python -m pip install oss2
)

echo.
echo Dependencies check completed, starting program...
echo.

python main.py
if errorlevel 1 (
    echo.
    echo Startup failed! Please check error messages
    echo If dependency issues, manually run: pip install customtkinter Pillow requests pyperclip tkcalendar pystray oss2
    pause
)