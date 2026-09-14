@echo off
chcp 65001 >nul
:: register_tasks.bat — Register tasks in Windows Task Scheduler
:: Requires: Run as Administrator

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

echo ==========================================
echo Register Windows Task Scheduler Tasks
echo ==========================================
echo.

:: Check admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Administrator rights required.
    echo Run cmd as Administrator.
    pause
    exit /b 1
)

set "BACKUP_SCRIPT=%PROJECT_DIR%\scripts\backup.bat"
set "HEALTH_SCRIPT=%PROJECT_DIR%\scripts\health_check.bat"

echo Project: %PROJECT_DIR%
echo.

:: 1. Daily backup at 03:00
echo [1/2] Registering daily backup (03:00)...
schtasks /Create /TN "VKBot_Backup" ^
    /TR "\"%BACKUP_SCRIPT%\" \"%PROJECT_DIR%\"" ^
    /SC DAILY /ST 03:00 ^
    /RL HIGHEST /F

if errorlevel 1 (
    echo [FAIL] Failed to create backup task
) else (
    echo [OK] Backup task registered (daily 03:00)
)

:: 2. Health-check every 5 minutes
echo.
echo [2/2] Registering health-check (every 5 min)...
schtasks /Create /TN "VKBot_HealthCheck" ^
    /TR "\"%HEALTH_SCRIPT%\" \"%PROJECT_DIR%\"" ^
    /SC MINUTE /MO 5 ^
    /RL HIGHEST /F

if errorlevel 1 (
    echo [FAIL] Failed to create health-check task
) else (
    echo [OK] Health-check task registered (every 5 min)
)

echo.
echo ==========================================
echo Done. Check in taskschd.msc:
echo   VKBot_Backup      - daily at 03:00
echo   VKBot_HealthCheck - every 5 minutes
echo ==========================================
echo.
echo To remove:
echo   schtasks /Delete /TN "VKBot_Backup" /F
echo   schtasks /Delete /TN "VKBot_HealthCheck" /F
echo.
pause