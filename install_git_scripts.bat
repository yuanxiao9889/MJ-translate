@echo off  
setlocal enabledelayedexpansion  
cd /d " "%%~dp0  
  
echo Git�ű���װ����  
  
if not exist git_upload.bat (  
    echo �����Ҳ���git_upload.bat�ļ�  
    pause  
    exit /b 1  
)  
  
echo �ű��ļ�������  
echo �ű����ڵ�ǰĿ¼����ֱ��ʹ��  
  
echo ʹ�÷�����  
echo   ˫�� git_upload.bat  
echo   �������������� .\git_upload.bat  
  
echo ��װ��ɣ�  
pause 
