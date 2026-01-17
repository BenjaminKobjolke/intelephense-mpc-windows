@echo off
if "%~1"=="" (
    echo Usage: search.bat QUERY [FOLDER]
    echo Example: search.bat MyClass
    exit /b 1
)
set QUERY=%~1
set FOLDER=%~2
if "%FOLDER%"=="" set FOLDER=.
uv run intelephense-watcher %FOLDER% --search %QUERY%
