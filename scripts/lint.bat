@echo off
chcp 65001 >nul
:: lint.bat — Run linting (ruff, mypy, black)

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%CD%"
popd

echo ==========================================
echo VK Bot - Linting & Type Checking
echo ==========================================

set "VENV=%PROJECT_DIR%\venv\Scripts"
set "FAILED=0"

echo.
echo [1/3] ruff (linting)...
%VENV%\python.exe -m ruff check src --line-length=120 --ignore=E203
if errorlevel 1 (
    echo [FAIL] ruff: errors found
    set "FAILED=1"
) else (
    echo [OK] ruff
)

echo.
echo [2/3] mypy (types)...
%VENV%\mypy.exe src --ignore-missing-imports --no-error-summary
if errorlevel 1 (
    echo [FAIL] mypy: type errors
    set "FAILED=1"
) else (
    echo [OK] mypy
)

echo.
echo [3/3] black (format check)...
%VENV%\black.exe src --line-length=120 --check
if errorlevel 1 (
    echo [FAIL] black: formatting needed (run format.bat)
    set "FAILED=1"
) else (
    echo [OK] black
)

echo.
if %FAILED%==1 (
    echo ==========================================
    echo [FAIL] Linting failed.
    echo Run format.bat to auto-fix.
    echo ==========================================
    pause
    exit /b 1
) else (
    echo ==========================================
    echo [OK] All checks passed.
    echo ==========================================
    pause
    exit /b 0
)