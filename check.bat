@echo off
if "%~1"=="" (
    echo Usage: check.bat FILE [FOLDER]
    echo Example: check.bat src/MyClass.php
    exit /b 1
)
set FILE=%~1
set FOLDER=%~2
if "%FOLDER%"=="" set FOLDER=.
call uv run intelephense-watcher %FOLDER% --file %FILE%
