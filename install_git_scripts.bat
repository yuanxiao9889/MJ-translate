@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo        Git 脚本安装器
echo ========================================
echo.

echo [信息] 正在安装Git推送和拉取脚本...
echo.

:: 检查当前目录是否包含脚本文件
if not exist "git_push.bat" (
    echo [错误] 找不到 git_push.bat 文件！
    echo 请确保在包含脚本文件的目录下运行此安装器。
    pause
    exit /b 1
)

if not exist "git_pull.bat" (
    echo [错误] 找不到 git_pull.bat 文件！
    echo 请确保在包含脚本文件的目录下运行此安装器。
    pause
    exit /b 1
)

:: 获取当前目录
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo [信息] 脚本位置: %SCRIPT_DIR%
echo.

:: 询问安装选项
echo 请选择安装选项：
echo 1. 仅在当前项目使用（推荐）
echo 2. 全局安装（添加到系统PATH）
echo 3. 创建桌面快捷方式
echo 4. 全部安装
echo.
set /p install_option="请输入选项 (1-4，默认1): "
if "!install_option!"=="" set install_option=1

:: 验证Git安装
echo [信息] 检查Git安装状态...
git --version >nul 2>&1
if errorlevel 1 (
    echo [警告] Git未安装或不在PATH中！
    echo [信息] 请先安装Git: https://git-scm.com/
    echo [信息] 脚本安装将继续，但需要Git才能正常工作。
    echo.
    pause
)

:: 检查是否在Git仓库中
if exist ".git" (
    echo [信息] 检测到Git仓库，脚本可以直接使用。
else
    echo [警告] 当前目录不是Git仓库。
    echo [信息] 脚本安装后需要在Git仓库目录中使用。
fi
echo.

:: 执行安装选项
if "!install_option!"=="1" goto :local_install
if "!install_option!"=="2" goto :global_install
if "!install_option!"=="3" goto :desktop_install
if "!install_option!"=="4" goto :full_install

echo [错误] 无效的选项！
pause
exit /b 1

:local_install
echo [信息] 本地安装完成！
echo [信息] 您可以直接使用以下命令：
echo   - git_push.bat  (推送代码)
echo   - git_pull.bat  (拉取代码)
goto :install_complete

:global_install
echo [信息] 正在进行全局安装...

:: 检查是否有管理员权限
net session >nul 2>&1
if errorlevel 1 (
    echo [警告] 需要管理员权限来修改系统PATH。
    echo [信息] 请以管理员身份运行此脚本，或手动将以下路径添加到PATH：
    echo [路径] %SCRIPT_DIR%
    echo.
    goto :manual_path_instruction
)

:: 添加到系统PATH（需要管理员权限）
echo [信息] 正在添加到系统PATH...
setx PATH "%PATH%;%SCRIPT_DIR%" /M >nul 2>&1
if errorlevel 1 (
    echo [错误] 添加到PATH失败！
    goto :manual_path_instruction
) else (
    echo [成功] 已添加到系统PATH！
    echo [信息] 重启命令提示符后可在任何目录使用：
    echo   - git_push
    echo   - git_pull
)
goto :install_complete

:manual_path_instruction
echo [信息] 手动添加PATH的步骤：
echo 1. 右键"此电脑" -> "属性"
echo 2. 点击"高级系统设置"
echo 3. 点击"环境变量"
echo 4. 在"系统变量"中找到"Path"并编辑
echo 5. 添加路径：%SCRIPT_DIR%
echo 6. 确定并重启命令提示符
goto :install_complete

:desktop_install
echo [信息] 正在创建桌面快捷方式...

:: 获取桌面路径
for /f "tokens=3*" %%i in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set "DESKTOP=%%i %%j"
if "!DESKTOP!"=="" set "DESKTOP=%USERPROFILE%\Desktop"

:: 创建推送快捷方式
echo [信息] 创建Git推送快捷方式...
(
echo @echo off
echo cd /d "%SCRIPT_DIR%"
echo call git_push.bat
echo pause
) > "!DESKTOP!\Git推送.bat"

:: 创建拉取快捷方式
echo [信息] 创建Git拉取快捷方式...
(
echo @echo off
echo cd /d "%SCRIPT_DIR%"
echo call git_pull.bat
echo pause
) > "!DESKTOP!\Git拉取.bat"

echo [成功] 桌面快捷方式创建完成！
echo [信息] 您可以在桌面找到：
echo   - Git推送.bat
echo   - Git拉取.bat
goto :install_complete

:full_install
echo [信息] 正在进行完整安装...
echo.
call :global_install
echo.
call :desktop_install
goto :install_complete

:install_complete
echo.
echo ========================================
echo          安装完成！
echo ========================================
echo.
echo [信息] Git脚本安装成功！
echo [信息] 使用说明请查看：Git脚本使用说明.md
echo.
echo [提示] 脚本功能：
echo   ✓ 自动检测文件更改
echo   ✓ 交互式提交信息输入
echo   ✓ 智能冲突处理
echo   ✓ 详细操作反馈
echo   ✓ 跨平台支持
echo.
echo [下一步] 在Git仓库目录中运行脚本开始使用！
echo.
pause