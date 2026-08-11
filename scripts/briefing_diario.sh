#!/usr/bin/env bash
# Briefing diario de la herramienta de inversion personal (Linux y macOS).
#
# Refresca las alertas y escribe briefing_AAAA-MM-DD.txt, para que al abrir la
# herramienta por la manana ya este todo calculado.
#
# Instalacion:
#   1. chmod +x scripts/briefing_diario.sh
#   2. crontab -e
#   3. Anade una linea (ej. de lunes a viernes a las 07:30):
#        30 7 * * 1-5 /ruta/al/repo/scripts/briefing_diario.sh >> /ruta/al/repo/cron.log 2>&1
#
# UNA VEZ AL DIA ES SUFICIENTE. Las fuentes son gratuitas y dan cierres diarios:
# consultarlas mas a menudo las castiga sin darte nada. Y mirar la cartera a
# todas horas es una forma conocida de tomar peores decisiones.
#
# Esta herramienta es de SOLO LECTURA: no envia ordenes a ningun broker.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Pon aqui tu email: la SEC exige un User-Agent identificable.
export INVEST_CONTACT="${INVEST_CONTACT:-tu-email@ejemplo.com}"
# Opcional: export FINNHUB_API_KEY="tu_clave"

PYTHON="${PYTHON:-$REPO_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="python3"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') briefing diario ==="
"$PYTHON" backend/daily.py --quiet
echo "Listo."
