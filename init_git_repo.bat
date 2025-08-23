@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo        MJ-translate Git 初始化脚本
echo ========================================
echo.

echo [信息] 正在初始化 MJ-translate 项目的 Git 仓库...
echo [仓库] https://github.com/yuanxiao9889/MJ-translate.git
echo.

:: 检查Git是否安装
echo [检查] 验证Git安装状态...
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Git未安装或不在PATH中！
    echo [解决] 请先安装Git: https://git-scm.com/
    echo.
    pause
    exit /b 1
)
echo [成功] Git已安装

:: 检查当前Git状态
if exist ".git" (
    echo [检查] 发现现有Git仓库
    
    :: 检查远程仓库配置
    for /f "delims=" %%i in ('git remote get-url origin 2^>nul') do set "current_remote=%%i"
    
    if "!current_remote!"=="" (
        echo [配置] 添加远程仓库...
        git remote add origin https://github.com/yuanxiao9889/MJ-translate.git
        if errorlevel 1 (
            echo [错误] 添加远程仓库失败！
            pause
            exit /b 1
        )
        echo [成功] 远程仓库已添加
    ) else (
        if "!current_remote!"=="https://github.com/yuanxiao9889/MJ-translate.git" (
            echo [信息] 远程仓库配置正确
        ) else (
            echo [警告] 当前远程仓库: !current_remote!
            echo [询问] 是否更新为正确的仓库地址？
            set /p update_remote="更新远程仓库地址? (Y/n): "
            if /i "!update_remote!"=="" set update_remote=Y
            if /i "!update_remote!"=="Y" (
                git remote set-url origin https://github.com/yuanxiao9889/MJ-translate.git
                if errorlevel 1 (
                    echo [错误] 更新远程仓库失败！
                    pause
                    exit /b 1
                )
                echo [成功] 远程仓库已更新
            )
        )
    )
) else (
    echo [初始化] 创建新的Git仓库...
    git init
    if errorlevel 1 (
        echo [错误] Git仓库初始化失败！
        pause
        exit /b 1
    )
    echo [成功] Git仓库已初始化
    
    echo [配置] 添加远程仓库...
    git remote add origin https://github.com/yuanxiao9889/MJ-translate.git
    if errorlevel 1 (
        echo [错误] 添加远程仓库失败！
        pause
        exit /b 1
    )
    echo [成功] 远程仓库已添加
)

:: 检查当前分支
for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set "current_branch=%%i"
if "!current_branch!"=="" (
    echo [信息] 当前没有提交，将在首次提交后设置分支
    set "need_branch_setup=1"
) else (
    if "!current_branch!"=="main" (
        echo [信息] 当前分支: main (正确)
    ) else (
        echo [信息] 当前分支: !current_branch!
        echo [询问] 是否重命名为main分支？
        set /p rename_branch="重命名为main分支? (Y/n): "
        if /i "!rename_branch!"=="" set rename_branch=Y
        if /i "!rename_branch!"=="Y" (
            git branch -M main
            if errorlevel 1 (
                echo [错误] 分支重命名失败！
            ) else (
                echo [成功] 分支已重命名为main
            )
        )
    )
)

:: 检查工作区状态
echo.
echo [检查] 工作区状态...
git status --porcelain >nul 2>&1
if errorlevel 1 (
    echo [警告] 无法获取Git状态
) else (
    for /f %%i in ('git status --porcelain 2^>nul ^| find /c /v ""') do set "changes=%%i"
    if !changes! gtr 0 (
        echo [发现] !changes! 个文件有变更
        echo [询问] 是否添加所有文件并提交？
        set /p commit_changes="提交所有变更? (Y/n): "
        if /i "!commit_changes!"=="" set commit_changes=Y
        if /i "!commit_changes!"=="Y" (
            echo [执行] 添加所有文件...
            git add .
            if errorlevel 1 (
                echo [错误] 添加文件失败！
            ) else (
                echo [执行] 提交变更...
                git commit -m "Initial commit - MJ-translate project setup"
                if errorlevel 1 (
                    echo [错误] 提交失败！
                ) else (
                    echo [成功] 变更已提交
                    
                    :: 如果需要设置分支，现在设置
                    if "!need_branch_setup!"=="1" (
                        git branch -M main
                        echo [成功] 默认分支设置为main
                    )
                )
            )
        )
    ) else (
        echo [信息] 工作区干净，无需提交
    )
)

:: 测试远程连接
echo.
echo [测试] 检查远程仓库连接...
git ls-remote origin >nul 2>&1
if errorlevel 1 (
    echo [警告] 无法连接到远程仓库
    echo [原因] 可能的原因：
    echo   1. 网络连接问题
    echo   2. 仓库不存在或无访问权限
    echo   3. 需要配置Git凭据
    echo.
    echo [建议] 请确保：
    echo   - GitHub仓库已创建
    echo   - 网络连接正常
    echo   - Git凭据已配置
) else (
    echo [成功] 远程仓库连接正常
)

:: 显示当前配置
echo.
echo ========================================
echo          配置完成！
echo ========================================
echo.
echo [仓库信息]
for /f "delims=" %%i in ('git remote get-url origin 2^>nul') do echo   远程仓库: %%i
for /f "delims=" %%i in ('git branch --show-current 2^>nul') do echo   当前分支: %%i
echo.
echo [下一步操作]
echo   1. 使用 git_upload.bat 进行代码推送
echo   2. 使用 git status 查看仓库状态
echo   3. 使用 git log --oneline 查看提交历史
echo.
echo [快捷脚本]
echo   - git_upload.bat    : 一键推送代码
echo   - git_upload.ps1    : PowerShell版本推送脚本
echo.
echo 初始化完成！现在可以正常使用Git功能了。
echo.
pause