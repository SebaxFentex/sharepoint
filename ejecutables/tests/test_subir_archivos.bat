@echo off
cd /d "%~dp0..\.."
uv run --env-file .env python tests/test_subir_archivos.py
set EXIT_CODE=%ERRORLEVEL%
echo.
echo Codigo de salida: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
