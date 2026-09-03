@echo off
title Ticket Sales System Launcher
cd /d %~dp0

set "MYSQLD=C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe"
set "MYSQLADMIN=C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqladmin.exe"
set "DATA=%~dp0..\.mysql\data"

echo [1/3] Checking MySQL database...
"%MYSQLADMIN%" -h 127.0.0.1 -P 3306 -u root -pWqy0813 ping 2>nul | find "alive" >nul
if not errorlevel 1 (
  echo       MySQL is already running.
  goto :deps
)
REM 独立数据库存在则启动它；否则假设组员使用自己安装的 MySQL 服务
if exist "%MYSQLD%" if exist "%DATA%\mysql" (
  echo       Starting bundled MySQL on port 3306 ...
  start "MySQL-TicketDB" /min "%MYSQLD%" --datadir="%DATA%" --port=3306 --mysqlx=0 --shared-memory=0 --console
  echo       Waiting for MySQL ...
  "%MYSQLADMIN%" -h 127.0.0.1 -P 3306 -u root -pWqy0813 --wait=30 ping 2>nul
) else (
  echo       [提示] 未检测到内置数据库，请确认你自己安装的 MySQL 服务已启动、
  echo              且已用 Navicat 导入 ddl.sql + seed_data.sql，config.py 密码已改好。
)

:deps
echo [2/3] Checking Python dependencies ...
python -m pip install -r requirements.txt

echo [3/3] Starting website ...
echo.
echo ==========================================
echo   Website : http://127.0.0.1:5000
echo   Accounts: zhang_san / admin   Password: 123456
echo   Keep this window open. Ctrl+C to stop.
echo ==========================================
echo.
python app.py
pause
