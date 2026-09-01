@echo off
title Tailwind CSS Watcher
echo ========================================
echo INICIANDO TAILWIND CSS (WATCH MODE)
echo ========================================

cd /d "%~dp0.."

if not exist node_modules (
    echo [INFO] No se encontro node_modules. Instalando dependencias de Node...
    call npm install
)

echo [INFO] Iniciando compilacion dinamica...
npm run watch
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Hubo un problema al ejecutar Tailwind.
    echo Asegurate de tener Node.js instalado.
    pause
)
pause
