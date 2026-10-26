@echo off
cd /d "%~dp0.."
if exist ".env" (
    uv run --env-file .env python -m sharepoint.autenticacion
) else (
    uv run python -m sharepoint.autenticacion
)
if errorlevel 1 pause
