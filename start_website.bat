@echo off
title Ticket Sales System Launcher
set "ROOT=%~dp0"
if not defined MYSQL_BIN set "MYSQL_BIN=%ProgramFiles%\MySQL\MySQL Server 8.0\bin"
if not defined MYSQLD set "MYSQLD=%MYSQL_BIN%\mysqld.exe"
if not defined MYSQLADMIN set "MYSQLADMIN=%MYSQL_BIN%\mysqladmin.exe"
if not defined MYSQL set "MYSQL=%MYSQL_BIN%\mysql.exe"
if not defined PY set "PY=python"
if not defined DB_USER set "DB_USER=root"
if not defined DB_PASSWORD set "DB_PASSWORD="
if not defined DB_PORT set "DB_PORT=3306"
if not defined DATA set "DATA=%ROOT%.mysql\data"

echo ==========================================
echo   Ticket Sales System Launcher
echo ==========================================

if defined DB_PASSWORD (set "MYSQL_AUTH=-p%DB_PASSWORD%") else (set "MYSQL_AUTH=")

REM ---- 1. check/start MySQL ----
echo [1/3] Checking MySQL ...
"%MYSQLADMIN%" -h 127.0.0.1 -P %DB_PORT% -u %DB_USER% %MYSQL_AUTH% ping 2>nul | findstr "alive" >nul
if not errorlevel 1 (
  echo       MySQL is already running.
) else if exist "%MYSQLD%" if exist "%DATA%\mysql" (
  echo       Starting bundled MySQL ...
  start "MySQL-TicketDB" /min "%MYSQLD%" --datadir="%DATA%" --port=%DB_PORT% --mysqlx=0 --shared-memory=0 --console
  echo       Waiting for MySQL ...
  "%MYSQLADMIN%" -h 127.0.0.1 -P %DB_PORT% -u %DB_USER% %MYSQL_AUTH% --wait=30 ping 2>nul | findstr "alive" >nul
  if errorlevel 1 (
    echo       [ERROR] MySQL start failed. Check .mysql folder.
    pause
    exit /b 1
  )
) else (
  echo       [WARN] No bundled MySQL found. Start your own MySQL service first.
)

REM ---- 2. verify DB ----
echo [2/3] Verifying database ...
"%MYSQL%" -h 127.0.0.1 -P %DB_PORT% -u %DB_USER% %MYSQL_AUTH% -e "SELECT COUNT(*) FROM ticket_sales.show_item;" >nul 2>&1
if errorlevel 1 (
  echo       [ERROR] Cannot connect DB or ticket_sales missing.
  echo       Import sql\schema\ddl.sql and sql\seed\seed_data.sql via Navicat first.
  pause
  exit /b 1
)
echo       Database OK.

REM ---- 3. start website ----
echo [3/3] Starting website ...

REM 检查 5000 端口是否已被占用（避免“Address already in use”运行失败）
netstat -ano | findstr ":5000 " | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo.
  echo   [INFO] Port 5000 is already in use — the website is probably already running.
  echo   ----------------------------------------------------------
  echo     Open in browser:  http://127.0.0.1:5000/
  echo     (New frontend, root path auto-jumps to /app/)
  echo     Accounts: zhang_san / admin   Password: 123456
  echo   ----------------------------------------------------------
  echo   If it is NOT responding, close this window, then kill the
  echo   process holding port 5000 and run this launcher again.
  echo   (netstat -ano ^| findstr :5000  →  taskkill /PID <pid> /F)
  pause
  exit /b 0
)

cd /d "%ROOT%backend"
echo.
echo ==========================================
echo   Website : http://127.0.0.1:5000/
echo   Accounts: zhang_san / admin  Password: 123456
echo   Close this window to stop the server.
echo ==========================================
echo.
"%PY%" app.py
pause
