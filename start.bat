@echo off
chcp 65001 >nul
title OceanSource - 资源查询服务

echo.
echo   ╔══════════════════════════════════════╗
echo   ║     OceanSource 资源查询服务         ║
echo   ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0backend"

echo [1/2] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

echo [2/2] 安装依赖并启动服务...
pip install -r requirements.txt -q
echo.
python server.py

pause