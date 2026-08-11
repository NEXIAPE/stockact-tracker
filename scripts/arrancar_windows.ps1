# Arranca la herramienta en Windows (PowerShell).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\arrancar_windows.ps1
#
# Abre dos ventanas nuevas (el motor y la interfaz) y luego el navegador.
# Para apagar la herramienta, cierra esas dos ventanas.
#
# Si es la primera vez, ejecuta antes scripts\instalar_windows.ps1
#
# Esta herramienta es de SOLO LECTURA: no envia ordenes a ningun broker.

$ErrorActionPreference = 'Stop'

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

$VenvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
$EnvFile = Join-Path $RepoDir ".env"

if (-not (Test-Path $VenvPython)) {
    Write-Host "No encuentro el entorno virtual." -ForegroundColor Red
    Write-Host "Ejecuta primero:" -ForegroundColor Yellow
    Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1" -ForegroundColor Cyan
    exit 1
}

# La configuracion la lee la propia aplicacion desde .env; aqui solo se avisa
# si falta, para no arrancar en silencio identificandose como el ejemplo.
if (-not (Test-Path $EnvFile)) {
    Write-Host "AVISO: no existe el archivo .env con tu email de contacto." -ForegroundColor Yellow
    Write-Host "       La SEC puede rechazar las consultas de fundamentales." -ForegroundColor Yellow
    Write-Host "       Copia .env.example como .env y pon tu email." -ForegroundColor Yellow
    Write-Host ""
}


# --- Motor (API) -----------------------------------------------------------
Write-Host "Arrancando el motor en http://127.0.0.1:8000 ..." -ForegroundColor Cyan

$comandoBackend = @"
Set-Location '$RepoDir'
Write-Host 'MOTOR DE LA HERRAMIENTA - no cierres esta ventana mientras la uses' -ForegroundColor Cyan
& '$VenvPython' -m uvicorn app.main:app --app-dir backend --reload
"@

Start-Process powershell -ArgumentList '-NoExit', '-Command', $comandoBackend

# Espera a que el motor responda antes de seguir.
$listo = $false
foreach ($intento in 1..30) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $listo = $true; break }
    } catch {
        # Todavia arrancando; se reintenta.
    }
}

if ($listo) {
    Write-Host "  Motor listo." -ForegroundColor Green
} else {
    Write-Host "  El motor tarda mas de lo normal. Mira la ventana que se abrio:" -ForegroundColor Yellow
    Write-Host "  si hay un error en rojo, ese es el problema." -ForegroundColor Yellow
}


# --- Interfaz --------------------------------------------------------------
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Yellow
    Write-Host "FALTA NODE.JS - por eso no se abre ninguna ventana" -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  El motor SI esta funcionando, pero la interfaz web necesita Node.js."
    Write-Host ""
    Write-Host "  1. Descarga la version LTS desde https://nodejs.org/" -ForegroundColor Cyan
    Write-Host "  2. Instala con las opciones por defecto." -ForegroundColor Cyan
    Write-Host "  3. CIERRA PowerShell por completo y vuelve a abrirlo." -ForegroundColor Cyan
    Write-Host "     (si no, Windows no ve el programa recien instalado)" -ForegroundColor DarkGray
    Write-Host "  4. Comprueba con: node --version" -ForegroundColor Cyan
    Write-Host "  5. Vuelve a ejecutar este mismo script." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Mientras tanto puedes usar la API en http://127.0.0.1:8000/docs"
    Write-Host "  y el briefing en texto con:"
    Write-Host "      .venv\Scripts\python.exe backend\daily.py" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

$FrontDir = Join-Path $RepoDir "frontend"
if (-not (Test-Path (Join-Path $FrontDir "node_modules"))) {
    Write-Host "Instalando la interfaz por primera vez (tarda un par de minutos) ..." -ForegroundColor Cyan
    Push-Location $FrontDir
    npm install
    Pop-Location
}

Write-Host "Arrancando la interfaz en http://localhost:5173 ..." -ForegroundColor Cyan

$comandoFrontend = @"
Set-Location '$FrontDir'
Write-Host 'INTERFAZ - no cierres esta ventana mientras la uses' -ForegroundColor Cyan
npm run dev
"@

Start-Process powershell -ArgumentList '-NoExit', '-Command', $comandoFrontend

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host ("=" * 70) -ForegroundColor DarkGray
Write-Host "Listo. La herramienta esta abierta en el navegador." -ForegroundColor Green
Write-Host ""
Write-Host "  Primera vez: completa tu Perfil, luego registra tu Cartera y tu efectivo."
Write-Host "  Para apagarla: cierra las dos ventanas que se abrieron."
Write-Host ""
Write-Host "  Recuerda: SOLO LECTURA. Nunca envia ordenes a tu broker."
Write-Host ("=" * 70) -ForegroundColor DarkGray
