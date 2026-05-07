@echo off
REM 番茄钟启动脚本
set "PYTHON_PATH=C:\Users\12037\AppData\Local\Programs\Python\Python312"
set "PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%PATH%"
start "" "%PYTHON_PATH%\pythonw.exe" "%~dp0pomodoro.py"
