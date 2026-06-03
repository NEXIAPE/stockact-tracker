#!/usr/bin/env bash
# Cron para macOS. Ejecuta el rastreador una vez al dia.
#
# Instalacion:
#   1. chmod +x scripts/cron_mac.sh
#   2. crontab -e
#   3. Anade una linea (ej. todos los dias a las 08:00):
#        0 8 * * * /ruta/al/repo/scripts/cron_mac.sh >> /ruta/al/repo/cron.log 2>&1
#
# NOTA: respeta los rate limits de las fuentes oficiales. No bajes la frecuencia
# a algo agresivo; una vez al dia es mas que suficiente (los PTR llegan con
# desfase de hasta ~45 dias).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Usa python3 del sistema o un venv si lo tienes.
PYTHON="${PYTHON:-python3}"

"$PYTHON" main.py
