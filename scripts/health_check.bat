@echo off
:: health_check.bat — Проверка работоспособности бота для мониторинга
:: Возвращает: 0 = OK, 1 = ошибка
:: Использование: health_check.bat [путь_к_проекту]

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

if "%~1" neq "" (
    set "PROJECT_DIR=%~1"
)

set "PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"
set "SCRIPT=%PROJECT_DIR%\scripts\health_check.py"

if not exist "%SCRIPT%" (
    echo [FAIL] health_check.py not found
    exit /b 1
)

"%PYTHON%" "%SCRIPT%"
exit /b %errorlevel%