"""Configuración de la edición personal.

Todo por variables de entorno, con valores por defecto que funcionan sin
configurar nada. La única clave opcional es la de Finnhub (plan gratuito): sin
ella la herramienta sigue funcionando con las fuentes sin clave.
"""

from __future__ import annotations

import os
from pathlib import Path

# Raíz del repositorio (contiene el rastreador STOCK Act heredado).
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

# Base de datos de la herramienta personal (perfil, cartera, watchlist, alertas).
DB_PATH = Path(os.getenv("INVEST_DB", REPO_ROOT / "personal_invest.db"))

# Base de datos del rastreador STOCK Act ya existente en el repo. Se usa SÓLO
# como señal de contexto opcional; si no existe, no pasa nada.
STOCKACT_DB_PATH = Path(os.getenv("STOCKACT_DB", REPO_ROOT / "stockact.db"))

# Caché en disco de respuestas de proveedores (evita golpear las fuentes).
CACHE_DIR = Path(os.getenv("INVEST_CACHE", REPO_ROOT / ".data_cache"))

# Contacto para el User-Agent. Las fuentes oficiales (SEC) lo exigen.
CONTACT_EMAIL = os.getenv("INVEST_CONTACT", "usuario-personal@example.com")
USER_AGENT = f"herramienta-inversion-personal/1.0 ({CONTACT_EMAIL})"

# --- Fuentes -------------------------------------------------------------
# Opción B elegida: fuentes sin clave + una clave gratuita opcional.
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
FINNHUB_ENABLED = bool(FINNHUB_API_KEY)

# Frescura: a partir de estos días, un dato se marca como "viejo" y baja la
# confianza de la recomendación.
STALE_PRICE_DAYS = int(os.getenv("STALE_PRICE_DAYS", "5"))
STALE_FUNDAMENTALS_DAYS = int(os.getenv("STALE_FUNDAMENTALS_DAYS", "200"))

# TTL de caché por tipo de dato (segundos).
CACHE_TTL = {
    "prices": 60 * 60 * 6,        # cierres diarios: 6 h basta
    "quote": 60 * 15,
    "fundamentals": 60 * 60 * 24 * 7,
    "news": 60 * 60 * 2,
    "tickermap": 60 * 60 * 24 * 30,
    "metrics": 60 * 60 * 24,
}

# CORS para el frontend de desarrollo (Vite).
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "INVEST_CORS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
