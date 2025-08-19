@echo off
chcp 65001 >nul
title MJ Translator - AI翻译工具
echo 正在启动 MJ Translator...
echo.

:: 检查并激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo 发现本地虚拟环境，正在激活...
    call venv\Scripts\activate.bat
    echo 虚拟环境已激活
) else (
    echo 未发现本地虚拟环境，使用系统Python
)
echo.

:: 检查Python是否可用
echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到Python，请先安装Python
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查并安装依赖
echo 检查依赖库...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo 正在安装tkinter...
    python -m pip install tk
)

python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo 正在安装customtkinter...
    python -m pip install customtkinter
)

python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo 正在安装Pillow...
    python -m pip install Pillow
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo 正在安装requests...
    python -m pip install requests
)

python -c "import pyperclip" >nul 2>&1
if errorlevel 1 (
    echo 正在安装pyperclip...
    python -m pip install pyperclip
)

python -c "import tkcalendar" >nul 2>&1
if errorlevel 1 (
    echo 正在安装tkcalendar...
    python -m pip install tkcalendar
)

python -c "import pystray" >nul 2>&1
if errorlevel 1 (
    echo 正在安装pystray...
    python -m pip install pystray
)

python -c "import oss2" >nul 2>&1
if errorlevel 1 (
    echo 正在安装oss2...
    python -m pip install oss2
)

echo.
echo 依赖检查完成，正在启动程序...
echo.

python main.py
if errorlevel 1 (
    echo.
    echo 启动失败！请检查错误信息
    echo 如果是依赖问题，请手动运行: pip install customtkinter Pillow requests pyperclip tkcalendar pystray oss2
    pause
)