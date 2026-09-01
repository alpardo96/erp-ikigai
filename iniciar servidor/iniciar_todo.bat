@echo off
title Iniciar Proyecto
echo ========================================
echo LANZANDO SERVICIOS DEL PROYECTO
echo ========================================

cd /d "%~dp0"

echo [1/2] Lanzando Django...
start "Django Server" cmd /c "django.bat"

echo [2/2] Lanzando Tailwind...
start "Tailwind Watcher" cmd /c "tailwind.bat"

echo.
echo [OK] Ambos procesos han sido lanzados en ventanas separadas.
echo Podes cerrar esta ventana.
timeout /t 5
exit
