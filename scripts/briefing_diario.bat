@echo off
REM Briefing diario de la herramienta de inversion personal (Windows).
REM
REM Instalacion con el Programador de tareas:
REM   1. Abre "Programador de tareas" -> Crear tarea basica.
REM   2. Desencadenador: diariamente, p. ej. a las 07:30.
REM   3. Accion: iniciar un programa -> esta ruta a briefing_diario.bat
REM
REM UNA VEZ AL DIA ES SUFICIENTE: las fuentes dan cierres diarios.
REM Esta herramienta es de SOLO LECTURA: no envia ordenes a ningun broker.

setlocal
set "REPO_DIR=%~dp0.."
cd /d "%REPO_DIR%"

REM Pon aqui tu email: la SEC exige un User-Agent identificable.
if "%INVEST_CONTACT%"=="" set "INVEST_CONTACT=tu-email@ejemplo.com"
REM Opcional: set "FINNHUB_API_KEY=tu_clave"

set "PY=%REPO_DIR%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo === %date% %time% briefing diario ===
"%PY%" backend\daily.py --quiet
echo Listo.
endlocal
