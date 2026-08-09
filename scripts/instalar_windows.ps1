# Instalacion en Windows (PowerShell). Ejecutar UNA SOLA VEZ.
#
# Uso:
#   1. Abre PowerShell en la carpeta del repositorio.
#   2. Ejecuta:
#        powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1
#
#   (El "-ExecutionPolicy Bypass" hace falta porque Windows bloquea por defecto
#    los scripts descargados. No cambia nada permanente en tu sistema: solo
#    aplica a esta ejecucion.)
#
# Que hace: comprueba Python y Node, crea el entorno virtual, instala las
# dependencias, guarda tu email de contacto y comprueba que las fuentes de datos
# te responden de verdad.
#
# Esta herramienta es de SOLO LECTURA: no envia ordenes a ningun broker.

$ErrorActionPreference = 'Stop'

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

function Titulo($texto) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor DarkGray
    Write-Host $texto -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor DarkGray
}

function Bien($texto)  { Write-Host "  OK    $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "  AVISO $texto" -ForegroundColor Yellow }
function Mal($texto)   { Write-Host "  FALLO $texto" -ForegroundColor Red }


# --- 1. Python -------------------------------------------------------------
Titulo "Paso 1 de 5 - Comprobando Python"

$PythonCmd = $null
foreach ($candidato in @('py', 'python', 'python3')) {
    $encontrado = Get-Command $candidato -ErrorAction SilentlyContinue
    if ($encontrado) {
        try {
            $version = & $candidato --version 2>&1
            if ($version -match '(\d+)\.(\d+)') {
                $mayor = [int]$Matches[1]
                $menor = [int]$Matches[2]
                if ($mayor -ge 3 -and $menor -ge 9) {
                    $PythonCmd = $candidato
                    Bien "$candidato -> $version"
                    break
                }
                Aviso "$candidato es $version (hace falta 3.9 o superior)"
            }
        } catch {
            # Ese candidato no responde; se prueba el siguiente.
        }
    }
}

if (-not $PythonCmd) {
    Mal "No se encontro Python 3.9 o superior."
    Write-Host ""
    Write-Host "  Instalalo desde https://www.python.org/downloads/"
    Write-Host "  IMPORTANTE: marca la casilla 'Add Python to PATH' durante la instalacion."
    Write-Host "  Luego CIERRA y vuelve a abrir PowerShell, y repite este script."
    exit 1
}


# --- 2. Node ---------------------------------------------------------------
Titulo "Paso 2 de 5 - Comprobando Node.js"

$NodeOk = $false
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = node --version
    if ($nodeVersion -match 'v(\d+)') {
        if ([int]$Matches[1] -ge 18) {
            Bien "node -> $nodeVersion"
            $NodeOk = $true
        } else {
            Aviso "node es $nodeVersion (hace falta v18 o superior)"
        }
    }
}

if (-not $NodeOk) {
    Aviso "No se encontro Node.js 18 o superior."
    Write-Host "  Instalalo desde https://nodejs.org/ (version LTS)."
    Write-Host "  Sin Node podras usar la API y el briefing en texto, pero NO la interfaz web."
}


# --- 3. Entorno virtual y dependencias -------------------------------------
Titulo "Paso 3 de 5 - Instalando el backend"

$VenvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "  Creando el entorno virtual en .venv ..."
    & $PythonCmd -m venv .venv
    if (-not (Test-Path $VenvPython)) {
        Mal "No se pudo crear el entorno virtual."
        exit 1
    }
    Bien "Entorno virtual creado."
} else {
    Bien "El entorno virtual ya existia."
}

Write-Host "  Instalando dependencias (esto tarda un minuto) ..."
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet -r (Join-Path $RepoDir "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Mal "Fallo la instalacion de dependencias. Revisa el mensaje de arriba."
    exit 1
}
Bien "Dependencias instaladas."


# --- 4. Tu email de contacto -----------------------------------------------
Titulo "Paso 4 de 5 - Tu email de contacto"

$EnvFile = Join-Path $RepoDir ".env"

if (Test-Path $EnvFile) {
    Bien "Ya tenias configuracion guardada en .env"
} else {
    Write-Host "  La SEC exige identificarse con un email para consultar sus datos."
    Write-Host "  Si no lo pones, puede bloquearte. No se envia a ningun otro sitio:"
    Write-Host "  solo viaja en la cabecera User-Agent de las consultas a la SEC."
    Write-Host ""
    $email = Read-Host "  Tu email"
    if ([string]::IsNullOrWhiteSpace($email)) {
        Aviso "Sin email. Podras seguir, pero la SEC quiza te rechace."
        $email = "usuario-personal@example.com"
    }

    Write-Host ""
    Write-Host "  Clave de Finnhub (OPCIONAL). Anade PER, beta y cotizacion mas fresca."
    Write-Host "  Se saca gratis en https://finnhub.io/. Deja en blanco para omitirla."
    $finnhub = Read-Host "  Clave de Finnhub"

    $lineas = @(
        "# Configuracion de la herramienta. NO se sube al repositorio.",
        "# La lee la aplicacion siempre, la lances como la lances.",
        "INVEST_CONTACT=$email"
    )
    if (-not [string]::IsNullOrWhiteSpace($finnhub)) {
        $lineas += "FINNHUB_API_KEY=$finnhub"
    }
    Set-Content -Path $EnvFile -Value $lineas -Encoding UTF8
    Bien "Guardado en .env"
}



# --- 5. Diagnostico de fuentes ---------------------------------------------
Titulo "Paso 5 de 5 - Comprobando que las fuentes te responden"

Write-Host "  Esto consulta Stooq, la SEC y los feeds de noticias de verdad."
Write-Host "  Tarda unos segundos: el cliente es lento a proposito para no abusar"
Write-Host "  de servicios gratuitos."
Write-Host ""

& $VenvPython (Join-Path $RepoDir "backend\diagnose.py")
$DiagOk = ($LASTEXITCODE -eq 0)


# --- Resumen ---------------------------------------------------------------
Titulo "RESUMEN"

if ($DiagOk) {
    Bien "Todo listo."
    Write-Host ""
    Write-Host "  Siguiente paso: arranca la herramienta con" -ForegroundColor White
    Write-Host ""
    Write-Host "      powershell -ExecutionPolicy Bypass -File scripts\arrancar_windows.ps1" -ForegroundColor Cyan
    Write-Host ""
} else {
    Mal "Alguna fuente obligatoria no respondio."
    Write-Host ""
    Write-Host "  Sin precios la herramienta no puede analizar nada, asi que conviene"
    Write-Host "  resolverlo antes de seguir. Causas habituales:"
    Write-Host "    - Un antivirus o cortafuegos corporativo bloqueando la salida."
    Write-Host "    - Una VPN activa."
    Write-Host "    - Falta de conexion en ese momento."
    Write-Host ""
    Write-Host "  Para comprobar a mano si tu red llega a la fuente de precios:"
    Write-Host "      curl.exe -I https://stooq.com" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Puedes repetir el diagnostico cuando quieras con:"
    Write-Host "      .venv\Scripts\python.exe backend\diagnose.py" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "  Recuerda: esta herramienta es de SOLO LECTURA. Sugiere y explica, pero"
Write-Host "  nunca envia ordenes ni se conecta a tu broker. Y no es asesoria"
Write-Host "  financiera ni tributaria."
Write-Host ""
