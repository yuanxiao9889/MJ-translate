@echo off  
setlocal enabledelayedexpansion  
cd /d " "%%~dp0  
  
echo Git�ֿ��ʼ���ű�  
  
git --version >nul 2>&1  
if errorlevel 1 (  
    echo Gitδ��װ�����Ȱ�װGit  
    pause  
    exit /b 1  
)  
echo Git�Ѱ�װ  
  
if exist .git (  
    echo ��������Git�ֿ�  
) else (  
    echo ��ʼ���µ�Git�ֿ�...  
    git init  
    git remote add origin https://github.com/yuanxiao9889/MJ-translate.git  
    echo Git�ֿ��ʼ�����  
)  
  
echo ���ڿ���ʹ��git_upload.bat���ʹ�����  
pause 
