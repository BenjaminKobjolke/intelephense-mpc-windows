@echo off
if "%~1"=="" (
    echo Usage: check.bat FILE [FOLDER] [--timeout SECONDS]
    echo Example: check.bat src/MyClass.php
    echo Example: check.bat src/MyClass.php D:\project --timeout 10
    exit /b 1
)
set FILE=%~1
set FOLDER=%~2
if "%FOLDER%"=="" set FOLDER=.
set TIMEOUT=%~3
set TIMEOUT_VAL=%~4
cd /d "%~dp0"
if "%TIMEOUT%"=="--timeout" (
    call uv run intelephense-watcher %FOLDER% --file %FILE% --timeout %TIMEOUT_VAL%
) else (
    call uv run intelephense-watcher %FOLDER% --file %FILE%
)
