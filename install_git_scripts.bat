@echo off  
setlocal enabledelayedexpansion  
cd /d " "%%~dp0  
  
echo Git脚本安装工具  
  
if not exist git_upload.bat (  
    echo 错误：找不到git_upload.bat文件  
    pause  
    exit /b 1  
)  
  
echo 脚本文件检查完成  
echo 脚本已在当前目录，可直接使用  
  
echo 使用方法：  
echo   双击 git_upload.bat  
echo   或在命令行运行 .\git_upload.bat  
  
echo 安装完成！  
pause 
