@echo off

echo 正在初始化conda...
call C:\ProgramData\miniconda3\Scripts\activate.bat

echo 切换到环境所在目录: I:\AI\APP\OpenOCR
cd /d I:\AI\APP\OpenOCR\OpenOCR

echo 正在激活环境...
call conda activate I:\AI\APP\OpenOCR

echo 成功激活环境!
python OpenOCR-GUI.py

echo 保持窗口打开...
cmd
    
