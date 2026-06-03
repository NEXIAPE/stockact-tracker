@echo off
REM Tarea programada para Windows. Ejecuta el rastreador una vez al dia.
REM
REM Instalacion (Programador de tareas):
REM   1. Abre "Programador de tareas" (Task Scheduler).
REM   2. Crear tarea basica -> Diariamente -> hora deseada (ej. 08:00).
REM   3. Accion: "Iniciar un programa" -> Programa/script:
REM        C:\ruta\al\repo\scripts\cron_windows.bat
REM
REM   O por linea de comandos:
REM     schtasks /Create /SC DAILY /TN "StockActTracker" /TR "C:\ruta\al\repo\scripts\cron_windows.bat" /ST 08:00
REM
REM NOTA: respeta los rate limits de las fuentes oficiales. Una vez al dia basta
REM (los PTR llegan con desfase de hasta ~45 dias).

setlocal
set "REPO_DIR=%~dp0.."
cd /d "%REPO_DIR%"

if "%PYTHON%"=="" set "PYTHON=python"

"%PYTHON%" main.py
endlocal
