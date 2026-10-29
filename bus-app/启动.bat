@echo off
chcp 65001 >nul
title 公交到站 - 本地服务（关掉本窗口即停止）
cd /d "%~dp0"

python --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo  [X] 这台电脑上没找到 Python。
  echo.
  echo      1. 打开 python.org/downloads 下载 Python 3
  echo      2. 安装第一步一定要勾选 "Add python.exe to PATH"
  echo      3. 装完之后重新双击本文件
  echo.
  pause
  exit /b 1
)

python server.py

echo.
echo  服务已停止。按任意键关闭窗口。
pause >nul
