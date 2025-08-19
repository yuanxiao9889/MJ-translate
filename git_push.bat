@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo           Git Push Script
echo ========================================
echo.

:: Check if in Git repository
if not exist ".git" (
    echo [ERROR] Current directory is not a Git repository!
    echo Please run this script in Git repository root directory.
    pause
    exit /b 1
)

:: Check if Git is installed
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed or not in PATH!
    echo Please install Git first: https://git-scm.com/
    pause
    exit /b 1
)

:: Show current status
echo [INFO] Checking current Git status...
git status --porcelain
if errorlevel 1 (
    echo [ERROR] Cannot get Git status!
    pause
    exit /b 1
)

:: Check for uncommitted changes
for /f %%i in ('git status --porcelain ^| find /c /v ""') do set changes=%%i
if !changes! equ 0 (
    echo [INFO] No changes to commit.
    echo.
    goto :push_only
)

echo.
echo [INFO] Found !changes! files with changes.
echo.

:: Show changed files
echo [INFO] List of changed files:
git status --short
echo.

:: Ask whether to add all files
set /p add_all="Add all changed files? (y/n, default y): "
if "!add_all!"=="" set add_all=y
if /i "!add_all!"=="n" (
    echo [INFO] Please manually add files to commit, then run this script again.
    pause
    exit /b 0
)

:: Add all changes
echo [INFO] Adding all changes to staging area...
git add .
if errorlevel 1 (
    echo [ERROR] Failed to add files!
    pause
    exit /b 1
)

:: Get commit message
set /p commit_msg="Enter commit message (default: Update code): "
if "!commit_msg!"=="" set commit_msg=Update code

:: Commit changes
echo [INFO] Committing changes...
git commit -m "!commit_msg!"
if errorlevel 1 (
    echo [ERROR] Commit failed!
    pause
    exit /b 1
)

:push_only
:: Get current branch
for /f "tokens=*" %%i in ('git branch --show-current') do set current_branch=%%i
if "!current_branch!"=="" (
    echo [ERROR] Cannot get current branch!
    pause
    exit /b 1
)

echo [INFO] Current branch: !current_branch!
echo.

:: Check remote repository
git remote -v >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No remote repository configured!
    echo Please add remote repository first: git remote add origin ^<repository-URL^>
    pause
    exit /b 1
)

:: Try to push
echo [INFO] Pushing to remote repository...
git push origin !current_branch!
if errorlevel 1 (
    echo.
    echo [WARNING] Push failed, may need to pull remote changes first.
    echo [INFO] Trying to pull remote changes...
    
    git pull origin !current_branch!
    if errorlevel 1 (
        echo [ERROR] Pull failed! There may be conflicts that need manual resolution.
        echo Please resolve conflicts manually and run this script again.
        pause
        exit /b 1
    )
    
    echo [INFO] Pull successful, trying to push again...
    git push origin !current_branch!
    if errorlevel 1 (
        echo [ERROR] Push still failed!
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo           Push Successful!
echo ========================================
echo [INFO] Code has been successfully pushed to remote repository.
echo [INFO] Branch: !current_branch!
echo.
pause