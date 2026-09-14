@echo off
chcp 65001 >nul
:: run.bat — Run bot in console (for dev/debug)

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

echo ==========================================
echo VK Bot - Console Run
echo ==========================================
echo Project: %PROJECT_DIR%
echo.

if not exist "%PROJECT_DIR%\venv\Scripts\python.exe" (
    echo [ERROR] Virtual env not found.
    echo Run: python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\.env" (
    echo [WARN] .env not found. Copying from .env.example...
    if exist "%PROJECT_DIR%\.env.example" (
        copy "%PROJECT_DIR%\.env.example" "%PROJECT_DIR%\.env" >nul
        echo [OK] .env created from template. EDIT IT BEFORE RUNNING!
        echo.
        pause
    ) else (
        echo [ERROR] .env.example not found.
        exit /b 1
    )
)

echo Starting bot...
echo Press Ctrl+C to stop.
echo.

"%PROJECT_DIR%\venv\Scripts\python.exe" "%PROJECT_DIR%\main.py"

echo.
echo Bot stopped.
pause