@echo off
chcp 65001 >nul
:: format.bat — Auto-format code (ruff --fix, black)

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

echo ==========================================
echo VK Bot - Auto-format
echo ==========================================

set "VENV=%PROJECT_DIR%\venv\Scripts"

echo.
echo [1/2] ruff --fix...
%VENV%\python.exe -m ruff check src --fix --line-length=120 --ignore=E203

echo.
echo [2/2] black...
%VENV%\black.exe src --line-length=120

echo.
echo [OK] Formatting done.
echo Run lint.bat to verify.
pause