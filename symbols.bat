@echo off
if "%~1"=="" (
    echo Usage: symbols.bat FILE [FOLDER]
    echo Example: symbols.bat src/MyClass.php
    exit /b 1
)
set FILE=%~1
set FOLDER=%~2
if "%FOLDER%"=="" set FOLDER=.
uv run intelephense-watcher %FOLDER% --symbols %FILE%
