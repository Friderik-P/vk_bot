@echo off
:: backup.bat — Бэкап базы данных SQLite для Windows Task Scheduler
:: Использование: backup.bat [путь_к_проекту]

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

if "%~1" neq "" (
    set "PROJECT_DIR=%~1"
)

set "PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"
set "SCRIPT=%PROJECT_DIR%\scripts\backup.py"

if not exist "%SCRIPT%" (
    echo [FAIL] backup.py not found
    exit /b 1
)

"%PYTHON%" "%SCRIPT%"
exit /b %errorlevel%