@echo off
cd /d "%~dp0.."
if exist ".env" (
    uv run --env-file .env -- python -m ms365.sharepoint.auth
) else (
    uv run python -m ms365.sharepoint.auth
)
if errorlevel 1 pause
