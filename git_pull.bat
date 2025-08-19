@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo           Git 拉取脚本
echo ========================================
echo.

:: 检查是否在Git仓库中
if not exist ".git" (
    echo [错误] 当前目录不是Git仓库！
    echo 请在Git仓库根目录下运行此脚本。
    pause
    exit /b 1
)

:: 检查Git是否安装
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Git未安装或不在PATH中！
    echo 请先安装Git: https://git-scm.com/
    pause
    exit /b 1
)

:: 获取当前分支
for /f "tokens=*" %%i in ('git branch --show-current') do set current_branch=%%i
if "!current_branch!"=="" (
    echo [错误] 无法获取当前分支！
    pause
    exit /b 1
)

echo [信息] 当前分支: !current_branch!
echo.

:: 检查远程仓库
git remote -v >nul 2>&1
if errorlevel 1 (
    echo [错误] 没有配置远程仓库！
    echo 请先添加远程仓库: git remote add origin <仓库URL>
    pause
    exit /b 1
)

:: 显示远程仓库信息
echo [信息] 远程仓库信息：
git remote -v
echo.

:: 检查本地是否有未提交的更改
for /f %%i in ('git status --porcelain ^| find /c /v ""') do set changes=%%i
if !changes! gtr 0 (
    echo [警告] 发现 !changes! 个未提交的更改：
    git status --short
    echo.
    set /p stash_changes="是否暂存这些更改？(y/n，默认y): "
    if "!stash_changes!"=="" set stash_changes=y
    
    if /i "!stash_changes!"=="y" (
        echo [信息] 暂存本地更改...
        git stash push -m "自动暂存 - %date% %time%"
        if errorlevel 1 (
            echo [错误] 暂存失败！
            pause
            exit /b 1
        )
        set stashed=1
    ) else (
        echo [警告] 继续拉取可能会导致冲突。
        set /p continue_pull="确定要继续吗？(y/n，默认n): "
        if "!continue_pull!"=="" set continue_pull=n
        if /i "!continue_pull!"=="n" (
            echo [信息] 操作已取消。
            pause
            exit /b 0
        )
    )
echo.
)

:: 获取远程更新信息
echo [信息] 获取远程仓库信息...
git fetch origin
if errorlevel 1 (
    echo [错误] 获取远程信息失败！
    pause
    exit /b 1
)

:: 检查是否有远程更新
for /f %%i in ('git rev-list HEAD..origin/!current_branch! --count 2^>nul') do set behind=%%i
if "!behind!"=="" set behind=0

for /f %%i in ('git rev-list origin/!current_branch!..HEAD --count 2^>nul') do set ahead=%%i
if "!ahead!"=="" set ahead=0

if !behind! equ 0 (
    echo [信息] 本地代码已是最新版本。
    if !ahead! gtr 0 (
        echo [信息] 本地有 !ahead! 个提交领先于远程。
    )
    goto :restore_stash
)

echo [信息] 远程有 !behind! 个新提交。
if !ahead! gtr 0 (
    echo [信息] 本地有 !ahead! 个提交领先于远程。
)
echo.

:: 显示即将拉取的提交
echo [信息] 即将拉取的提交：
git log --oneline HEAD..origin/!current_branch! --max-count=10
echo.

:: 执行拉取
echo [信息] 拉取远程更改...
if !ahead! gtr 0 (
    echo [信息] 使用rebase模式拉取以保持提交历史整洁...
    git pull --rebase origin !current_branch!
) else (
    git pull origin !current_branch!
)

if errorlevel 1 (
    echo [错误] 拉取失败！
    echo 可能存在冲突需要手动解决。
    echo.
    echo 冲突解决步骤：
    echo 1. 编辑冲突文件，解决冲突标记
    echo 2. 运行: git add <冲突文件>
    if !ahead! gtr 0 (
        echo 3. 运行: git rebase --continue
    ) else (
        echo 3. 运行: git commit
    )
    pause
    exit /b 1
)

:restore_stash
:: 恢复暂存的更改
if defined stashed (
    echo [信息] 恢复之前暂存的更改...
    git stash pop
    if errorlevel 1 (
        echo [警告] 恢复暂存更改时出现冲突！
        echo 请手动解决冲突后运行: git stash drop
    ) else (
        echo [信息] 暂存的更改已成功恢复。
    )
    echo.
)

echo ========================================
echo           拉取完成！
echo ========================================
echo [信息] 代码已成功从远程仓库拉取。
echo [信息] 分支: !current_branch!
echo.

:: 显示最新的几个提交
echo [信息] 最新提交记录：
git log --oneline --max-count=5
echo.
pause