@echo off
if "%~1"=="" (
    uv run intelephense-watcher . --capabilities
) else (
    uv run intelephense-watcher %* --capabilities
)
