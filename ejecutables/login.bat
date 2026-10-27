@echo off
cd /d "%~dp0.."
if exist ".env" (
    uv run --env-file .env python -m sharepoint
) else (
    uv run python -m sharepoint
)
if errorlevel 1 pause
