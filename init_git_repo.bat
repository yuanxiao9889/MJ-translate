@echo off  
setlocal enabledelayedexpansion  
cd /d " "%%~dp0  
  
echo Git仓库初始化脚本  
  
git --version >nul 2>&1  
if errorlevel 1 (  
    echo Git未安装，请先安装Git  
    pause  
    exit /b 1  
)  
echo Git已安装  
  
if exist .git (  
    echo 发现现有Git仓库  
) else (  
    echo 初始化新的Git仓库...  
    git init  
    git remote add origin https://github.com/yuanxiao9889/MJ-translate.git  
    echo Git仓库初始化完成  
)  
  
echo 现在可以使用git_upload.bat推送代码了  
pause 
