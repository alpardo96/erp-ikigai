@echo off
title RESPALDO DIARIO DE DESARROLLO - JM SOFT
color 1F

echo ========================================================
echo      GENERANDO COPIA DE SEGURIDAD (VERSIONADO)
echo ========================================================
echo.

:: --- 1. CONFIGURACION DE RUTAS ---
set "ORIGEN=D:\JM_Soft\erp-ikigai"
set "DESTINO_BASE=D:\JM_Soft\erp-ikigai_respaldo"

:: --- 2. OBTENER FECHA EN FORMATO AAAAMMDD ---
:: Esto asume tu fecha local DD/MM/AAAA (Ej: 09/02/2026)
set DIA=%DATE:~0,2%
set MES=%DATE:~3,2%
set ANIO=%DATE:~-4%

:: Formamos la carpeta final: D:\JM_Soft\DjangoContable_20260209
set "CARPETA_DESTINO=%DESTINO_BASE%_%ANIO%%MES%%DIA%"

echo Origen:  %ORIGEN%
echo Destino: %CARPETA_DESTINO%
echo.

if exist "%CARPETA_DESTINO%" (
    echo [AVISO] Ya existe un respaldo con fecha de hoy.
    echo Se actualizaran los archivos modificados en esa carpeta.
    echo.
    timeout /t 2 >nul
)

:: --- 3. EJECUTAR ROBOCOPY ---
:: /E  :: Copia subdirectorios (incluyendo vacíos)
:: /XO :: Excluye archivos más antiguos (solo actualiza lo nuevo si ya corriste el backup hoy)
:: /XD :: Excluye carpetas (Aquí sacamos venv y __pycache__)
:: /XF :: Excluye archivos (Aquí sacamos logs o temporales)

robocopy "%ORIGEN%" "%CARPETA_DESTINO%" /E /XO /XD "venv" ".git" "__pycache__" ".idea" ".vscode" /XF "*.log" "*.pyc" "*.tmp" "Respaldo"

echo.
echo ========================================================
if %ERRORLEVEL% LEQ 7 (
    color 2F
    echo    RESPALDO EXITOSO EN DISCO D:
) else (
    color 4F
    echo    HUBO ERRORES EN EL RESPALDO
)
echo ========================================================
echo.
pause