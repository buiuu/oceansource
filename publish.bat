@echo off
chcp 65001 >nul
title OceanSource - 公网发布工具
color 0A

echo.
echo   ╔══════════════════════════════════════════════════════════╗
echo   ║                OceanSource 公网发布工具                  ║
echo   ╚══════════════════════════════════════════════════════════╝
echo.

:: 检查 ngrok 是否已安装
where ngrok >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 ngrok，请先安装：
    echo    1. 打开 Microsoft Store
    echo    2. 搜索 "ngrok"
    echo    3. 安装 ngrok
    echo.
    pause
    exit /b 1
)

:: 检查是否已登录 ngrok
ngrok config check >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 首次使用需要登录 ngrok
    echo    1. 访问 https://dashboard.ngrok.com/signup
    echo    2. 注册账号（支持 GitHub/Google 登录）
    echo    3. 获取 authtoken
    echo    4. 运行命令：ngrok config add-authtoken <你的token>
    echo.
    echo 或者使用临时隧道（无需登录，但每次地址不同）
    set /p choice=使用临时隧道？(y/n): 
    if /i "%choice%"=="y" goto temp_tunnel
    pause
    exit /b 1
)

:start
echo.
echo [1/3] 启动本地后端服务...
start /B cmd /c "cd /d "%~dp0backend" && python server.py"
timeout /t 3 /nobreak >nul

echo [2/3] 检查本地服务...
curl -s http://localhost:5001/api/health >nul
if %errorlevel% neq 0 (
    echo [错误] 本地服务启动失败，请检查
    pause
    exit /b 1
)

echo [3/3] 创建公网隧道...
echo.
echo ═══════════════════════════════════════════════════════════
echo  重要：保持此窗口运行，不要关闭！
echo  隧道创建后，会显示公网地址（如 https://xxx.ngrok-free.app）
echo  将此地址分享给他人即可访问
echo ═══════════════════════════════════════════════════════════
echo.

:: 创建 ngrok 隧道
ngrok http 5001

goto end

:temp_tunnel
echo.
echo [使用临时隧道，无需登录]
echo 注意：每次重启地址会变化
echo.
ngrok http 5001 --basic-auth "user:oceansource"

:end
pause
exit /b 0