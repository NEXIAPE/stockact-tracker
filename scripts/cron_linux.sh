#!/usr/bin/env bash
# Cron para Linux. Ejecuta el rastreador una vez al dia.
#
# Instalacion:
#   1. chmod +x scripts/cron_linux.sh
#   2. crontab -e
#   3. Anade una linea (ej. todos los dias a las 08:00):
#        0 8 * * * /ruta/al/repo/scripts/cron_linux.sh >> /ruta/al/repo/cron.log 2>&1
#
# Alternativa systemd: crea un .service + .timer que ejecute este script.
#
# NOTA: respeta los rate limits de las fuentes oficiales. Una vez al dia basta
# (los PTR llegan con desfase de hasta ~45 dias).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

PYTHON="${PYTHON:-python3}"

"$PYTHON" main.py
