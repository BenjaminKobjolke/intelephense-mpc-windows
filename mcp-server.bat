@echo off
cd /d "%~dp0"
uv run python -m intelephense_watcher.mcp_server
