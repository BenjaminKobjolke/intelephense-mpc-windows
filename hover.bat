@echo off
if "%~1"=="" (
    echo Usage: hover.bat FILE LINE COL [FOLDER]
    echo Example: hover.bat src/MyClass.php 10 15
    exit /b 1
)
set FILE=%~1
set LINE=%~2
set COL=%~3
set FOLDER=%~4
if "%FOLDER%"=="" set FOLDER=.
uv run intelephense-watcher %FOLDER% --hover %FILE% %LINE% %COL%
