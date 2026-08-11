# Publica la herramienta en tu red privada de Tailscale, con HTTPS.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\publicar_tailscale.ps1
#
# QUE HACE Y QUE NO
# Deja la herramienta accesible desde tu movil, desde donde estes, con una
# direccion https estable. NO la publica en internet: solo la ven los
# dispositivos que tu hayas metido en tu Tailscale. Tus datos siguen en el
# disco de este ordenador y no se copian a ningun servidor de nadie.
#
# El motor escucha SOLO en 127.0.0.1 a proposito. Ni siquiera queda expuesto a
# tu red local: el unico que llega hasta el es el propio Tailscale, que corre
# en esta misma maquina.
#
# La herramienta sigue siendo de SOLO LECTURA: nunca envia ordenes a un broker.

$ErrorActionPreference = 'Stop'

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

$VenvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
$EnvFile    = Join-Path $RepoDir ".env"
$FrontDir   = Join-Path $RepoDir "frontend"
$Puerto     = 8000

function Fallo($mensaje, $arreglo) {
    Write-Host ""
    Write-Host "  $mensaje" -ForegroundColor Red
    Write-Host ""
    foreach ($linea in $arreglo) { Write-Host "    $linea" -ForegroundColor Cyan }
    Write-Host ""
    exit 1
}

Write-Host ("=" * 70) -ForegroundColor DarkGray
Write-Host "  Publicar en tu red privada (Tailscale)" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor DarkGray

if (-not (Test-Path $VenvPython)) {
    Fallo "No encuentro el entorno virtual." @(
        "powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1")
}

# --- 1. LA CONTRASENA. Esto es un cerrojo, no un aviso. --------------------
#
# En cuanto la herramienta deja de estar solo en 127.0.0.1, la contrasena pasa
# de ser opcional a ser lo unico que separa tu cartera de cualquiera que llegue
# a la direccion. Tailscale ya limita quien llega, pero un movil perdido y
# desbloqueado se salta esa capa entera. Este script se NIEGA a seguir sin ella.
$hashPuesto = $false
if (Test-Path $EnvFile) {
    foreach ($linea in (Get-Content $EnvFile -Encoding UTF8)) {
        if ($linea -match '^\s*APP_PASSWORD_HASH\s*=\s*\S+') { $hashPuesto = $true }
    }
}
if (-not $hashPuesto) {
    Fallo "No hay contrasena configurada, y no voy a publicar sin ella." @(
        "Generala con (te la pide sin mostrarla y solo guarda el hash):",
        "",
        "    .venv\Scripts\python.exe backend\set_password.py",
        "",
        "Y vuelve a ejecutar este script.")
}
Write-Host "  [1/5] Contrasena configurada." -ForegroundColor Green

# --- 2. Tailscale ----------------------------------------------------------
$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    $ruta = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $ruta) { $tailscale = $ruta } else {
        Fallo "Tailscale no esta instalado." @(
            "Instalalo desde https://tailscale.com/download  (plan personal, gratis)",
            "Inicia sesion, y despues instalalo tambien en tu movil con la MISMA cuenta.",
            "Luego vuelve a ejecutar este script.")
    }
} else { $tailscale = $tailscale.Source }

$estado = & $tailscale status 2>&1
if ($LASTEXITCODE -ne 0) {
    Fallo "Tailscale esta instalado pero no ha iniciado sesion." @(
        "    tailscale up",
        "",
        "Se abrira el navegador para que entres con tu cuenta.")
}
Write-Host "  [2/5] Tailscale conectado." -ForegroundColor Green

# --- 3. Interfaz compilada -------------------------------------------------
#
# Compilada, no en modo desarrollo: asi la sirve el MISMO proceso que la API.
# Con un solo origen la cookie de sesion no cruza dominios y SameSite=Strict
# puede protegerla de verdad.
if (-not (Test-Path (Join-Path $FrontDir "node_modules"))) {
    Write-Host "  Instalando dependencias de la interfaz (un par de minutos)..." -ForegroundColor Cyan
    Push-Location $FrontDir; npm install; Pop-Location
}
Write-Host "  [3/5] Compilando la interfaz..." -ForegroundColor Cyan
Push-Location $FrontDir
npm run build
$okBuild = $LASTEXITCODE -eq 0
Pop-Location
if (-not $okBuild) { Fallo "Fallo al compilar la interfaz." @("Revisa el error de npm de aqui arriba.") }

# --- 4. El motor, solo en 127.0.0.1 ----------------------------------------
Write-Host "  [4/5] Arrancando el motor en 127.0.0.1:$Puerto ..." -ForegroundColor Cyan
$comando = @"
Set-Location '$RepoDir'
Write-Host 'MOTOR - no cierres esta ventana mientras uses la herramienta' -ForegroundColor Cyan
Write-Host 'Escucha SOLO en 127.0.0.1. Quien llega desde fuera es Tailscale.' -ForegroundColor DarkGray
& '$VenvPython' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Puerto --proxy-headers
"@
Start-Process powershell -ArgumentList '-NoExit', '-Command', $comando
Start-Sleep -Seconds 6

# --- 5. El tunel -----------------------------------------------------------
#
# La sintaxis de "tailscale serve" ha cambiado entre versiones. Se prueban las
# formas conocidas y, si ninguna funciona, se muestra la ayuda del propio
# programa en lugar de dejarte con un error opaco: esa ayuda es la fuente
# fiable para TU version.
Write-Host "  [5/5] Publicando por HTTPS en tu red privada..." -ForegroundColor Cyan

$intentos = @(
    @('serve', '--bg', "$Puerto"),
    @('serve', '--bg', "http://127.0.0.1:$Puerto"),
    @('serve', 'https:443', '/', "http://127.0.0.1:$Puerto")
)
$publicado = $false
foreach ($args in $intentos) {
    & $tailscale @args 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $publicado = $true; break }
}

if (-not $publicado) {
    Write-Host ""
    Write-Host "  No pude publicar el tunel automaticamente." -ForegroundColor Yellow
    Write-Host "  El motor SI esta funcionando en http://127.0.0.1:$Puerto" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Esta es la ayuda de TU version de Tailscale, que manda sobre" -ForegroundColor Yellow
    Write-Host "  cualquier comando que yo pudiera adivinar:" -ForegroundColor Yellow
    Write-Host ""
    & $tailscale serve --help
    Write-Host ""
    Write-Host "  Busca el ejemplo que apunte a un puerto local y ejecutalo a mano." -ForegroundColor Cyan
    Write-Host "  Si dice que faltan los certificados HTTPS, actívalos en:" -ForegroundColor Cyan
    Write-Host "      https://login.tailscale.com/admin/dns   (seccion HTTPS Certificates)" -ForegroundColor Cyan
    exit 1
}

$dns = (& $tailscale status --json | ConvertFrom-Json).Self.DNSName
$url = "https://" + $dns.TrimEnd('.')

Write-Host ""
Write-Host ("=" * 70) -ForegroundColor DarkGray
Write-Host "  Listo. Tu herramienta esta en:" -ForegroundColor Green
Write-Host "      $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Abrela en el movil con Tailscale encendido y la misma cuenta." -ForegroundColor Gray
Write-Host "  Te pedira tu contrasena. La sesion dura 12 horas." -ForegroundColor Gray
Write-Host ""
Write-Host "  Para dejar de publicarla:    tailscale serve reset" -ForegroundColor Gray
Write-Host "  Para ver que hay publicado:  tailscale serve status" -ForegroundColor Gray
Write-Host ""
Write-Host "  Sigue siendo de SOLO LECTURA: nunca envia ordenes a tu broker." -ForegroundColor DarkGray
Write-Host ("=" * 70) -ForegroundColor DarkGray

Start-Process $url
