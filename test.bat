@echo off
chcp 65001 >nul
title OceanSource 快速测试
color 0A

echo.
echo   ╔══════════════════════════════════════╗
echo   ║        OceanSource 快速测试          ║
echo   ╚══════════════════════════════════════╝
echo.

echo [1/3] 检查本地访问...
curl -s http://localhost:5001/api/health >nul
if %errorlevel% equ 0 (
    echo  ✅ 本地服务正常
    echo     访问地址: http://localhost:5001
) else (
    echo  ❌ 本地服务未启动
    echo     请先运行 start.bat
    pause
    exit /b 1
)

echo.
echo [2/3] 检查网络访问（本机IP）...
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr "IPv4"') do (
    set "ip=%%i"
    set "ip=!ip:~1!"
    echo  ✅ 本机IP: !ip!
    echo     局域网地址: http://!ip!:5001
    goto :ip_found
)
:ip_found

echo.
echo [3/3] 生成公网访问二维码（可选）...
echo 如需公网访问，请运行 publish.bat
echo.

echo ═══════════════════════════════════════════════════════════
echo  测试方法：
echo  1. 电脑浏览器: http://localhost:5001
echo  2. 手机同WiFi: http://!ip!:5001
echo  3. 公网访问: 运行 publish.bat 获取地址
echo ═══════════════════════════════════════════════════════════
echo.

echo 按任意键打开本地网站...
pause >nul
start http://localhost:5001

echo 是否生成手机测试二维码？(y/n)
set /p choice=
if /i "%choice%"=="y" (
    echo 正在生成二维码...
    echo http://!ip!:5001 | curl -F "q=<-" https://qrcode.show -o qr.png 2>nul
    if exist qr.png (
        echo 二维码已保存为 qr.png
        start qr.png
    )
)

pause
exit /b 0