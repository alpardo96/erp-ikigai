@echo off
title Servidor Django
echo ========================================
echo INICIANDO SERVIDOR DJANGO
echo ========================================

cd /d "%~dp0.."

if not exist venv (
    echo [ERROR] No se encontro la carpeta venv en %CD%
    echo Por favor, contacta a soporte o recrea el entorno virtual.
    pause
    exit /b
)

set "PYTHON_EXE=venv\Scripts\python.exe"

echo [INFO] Verificando integridad del sistema...
"%PYTHON_EXE%" manage.py check
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Se detectaron errores en Django. El servidor no iniciara.
    pause
    exit /b
)

echo [OK] Sistema verificado.
echo [INFO] Iniciando servidor en http://127.0.0.1:8000
echo.
"%PYTHON_EXE%" manage.py runserver 0.0.0.0:8000
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] El servidor se cerro inesperadamente.
    pause
)
pause
