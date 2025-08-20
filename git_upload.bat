@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo =================================
echo     GitHub一键上传脚本
echo =================================
echo.

REM 检查PowerShell是否可用
powershell -Command "Get-Host" >nul 2>&1
if errorlevel 1 (
    echo 错误: 系统中未找到PowerShell
    echo 请确保Windows PowerShell已正确安装
    pause
    exit /b 1
)

REM 执行PowerShell脚本
powershell -ExecutionPolicy Bypass -File "%~dp0git_upload.ps1"

REM 检查执行结果
if errorlevel 1 (
    echo.
    echo 脚本执行过程中出现错误
    pause
    exit /b 1
)

exit /b 0