@echo off
chcp 65001 >nul
:: install_service.bat — Install VK Bot as Windows service via NSSM
:: Requires: NSSM (https://nssm.cc/download) in PATH or next to this script

setlocal enabledelayedexpansion

echo ==========================================
echo VK Bot - Install as Windows Service (NSSM)
echo ==========================================
echo.

:: Check NSSM
where nssm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] NSSM not found in PATH.
    echo Download: https://nssm.cc/download
    echo Place nssm.exe in this script's folder or add to PATH.
    pause
    exit /b 1
)

:: Project path
set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

echo Project: %PROJECT_DIR%
echo.

:: Check venv
if not exist "%PROJECT_DIR%\venv\Scripts\python.exe" (
    echo [ERROR] Virtual env not found: %PROJECT_DIR%\venv
    echo Run: python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Check .env
if not exist "%PROJECT_DIR%\.env" (
    echo [WARN] .env not found. Copy .env.example to .env and fill tokens.
)

:: Service name
set "SERVICE_NAME=VKBot"
set "DISPLAY_NAME=VK Bot with GigaChat"
set "DESCRIPTION=VK Bot with GigaChat - Long Poll bot for VK community"

:: Python path
set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
set "MAIN_SCRIPT=%PROJECT_DIR%\main.py"
set "WORK_DIR=%PROJECT_DIR%"

echo Installing service "%SERVICE_NAME%"...
echo Python: %PYTHON_EXE%
echo Script: %MAIN_SCRIPT%
echo Work dir: %WORK_DIR%
echo.

:: Install via NSSM
nssm install "%SERVICE_NAME%" "%PYTHON_EXE%" "%MAIN_SCRIPT%"
if errorlevel 1 (
    echo [ERROR] Failed to install service. Run as Administrator.
    pause
    exit /b 1
)

:: Configure
nssm set "%SERVICE_NAME%" AppDirectory "%WORK_DIR%"
nssm set "%SERVICE_NAME%" DisplayName "%DISPLAY_NAME%"
nssm set "%SERVICE_NAME%" Description "%DESCRIPTION%"
nssm set "%SERVICE_NAME%" AppStdout "%WORK_DIR%\logs\service.stdout.log"
nssm set "%SERVICE_NAME%" AppStderr "%WORK_DIR%\logs\service.stderr.log"
nssm set "%SERVICE_NAME%" AppRotateFiles 1
nssm set "%SERVICE_NAME%" AppRotateBytes 10485760
nssm set "%SERVICE_NAME%" AppEnvironmentExtra "PYTHONIOENCODING=utf-8"
nssm set "%SERVICE_NAME%" Start SERVICE_AUTO_START
nssm set "%SERVICE_NAME%" ObjectName "LocalSystem"
nssm set "%SERVICE_NAME%" Type SERVICE_WIN32_OWN_PROCESS

:: Restart on crash
nssm set "%SERVICE_NAME%" AppExit Default Restart
nssm set "%SERVICE_NAME%" AppThrottle 5000
nssm set "%SERVICE_NAME%" AppStopMethodSkip 6

echo.
echo [OK] Service "%SERVICE_NAME%" installed.
echo.
echo Commands:
echo   net start %SERVICE_NAME%       - start
echo   net stop %SERVICE_NAME%        - stop
echo   sc query %SERVICE_NAME%        - status
echo   nssm edit %SERVICE_NAME%       - edit params
echo   nssm remove %SERVICE_NAME% confirm - remove service
echo.
echo Service logs: %WORK_DIR%\logs\service.stdout.log / .stderr.log
echo Bot logs:     %WORK_DIR%\logs\bot.info.log / bot.error.log
echo.

pause