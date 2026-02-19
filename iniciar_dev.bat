@echo off
cls
echo ==========================================
echo   INICIANDO SERVIDOR DE DESENVOLVIMENTO
echo ==========================================
echo.
py -m uvicorn app:app --reload
pause