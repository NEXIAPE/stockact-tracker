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


# ---------------------------------------------------------------------------
# Archivo .env
# ---------------------------------------------------------------------------
# La configuración se lee de un archivo ``.env`` en la raíz del repositorio,
# no sólo de variables de entorno.
#
# Por qué: si la configuración vive únicamente en variables de entorno, sólo
# aplica al proceso que las exportó. Lanzar el diagnóstico o el briefing diario
# desde otra terminal las perdía, y la herramienta acababa identificándose ante
# la SEC con el email de ejemplo sin avisar de nada. Un archivo que lee la propia
# aplicación funciona igual la lances como la lances y en cualquier sistema.
#
# Precedencia: una variable de entorno real GANA sobre el archivo, para poder
# sobrescribir puntualmente sin editar nada.
ENV_FILE = Path(os.getenv("INVEST_ENV_FILE", REPO_ROOT / ".env"))


def _load_env_file(path: Path) -> dict:
    """Lee un .env sencillo (CLAVE=valor). Ignora comentarios y líneas vacías."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    # Los editores de Windows guardan en codificaciones distintas y el usuario no
    # tiene por qué saber cuál. Se prueban en orden:
    #   utf-8-sig  descarta el BOM que escribe PowerShell 5.1 con -Encoding UTF8.
    #              Sin esto, el BOM se pega a la PRIMERA clave ("﻿INVEST_CONTACT")
    #              y ese ajuste se ignora en silencio mientras los demás funcionan.
    #   utf-16     lo que produce el Bloc de notas al elegir "Unicode".
    #   latin-1    último recurso: nunca falla, aunque pueda deformar acentos.
    text = None
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError:
            return values

    if text is None:
        return values  # ilegible: se sigue con los valores por defecto

    for raw in text.splitlines():
        line = raw.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


_FILE_VALUES = _load_env_file(ENV_FILE)


def setting(name: str, default: str = "") -> str:
    """Valor de configuración: variable de entorno, si no el .env, si no el defecto."""
    from_env = os.getenv(name)
    if from_env is not None and from_env.strip() != "":
        return from_env
    return _FILE_VALUES.get(name, default)


def origin(name: str) -> str:
    """De DÓNDE viene un ajuste: «entorno», «.env» o «por defecto».

    Existe porque perseguir un ajuste que no se aplica es de las cosas más
    frustrantes que hay, y adivinar de dónde sale un valor no es forma de
    depurar. El diagnóstico lo muestra para que se vea de un vistazo si el
    archivo que estás editando es el que la herramienta realmente lee.
    """
    from_env = os.getenv(name)
    if from_env is not None and from_env.strip() != "":
        return "variable de entorno"
    if name in _FILE_VALUES:
        return f"{ENV_FILE.name}"
    return "por defecto"


# Ajustes que se muestran en el diagnóstico. El valor de la clave de Finnhub
# NUNCA se imprime: sólo si está puesta o no.
REPORTED_SETTINGS = [
    ("INVEST_CONTACT", False),
    ("PRICE_PROVIDERS", False),
    ("FINNHUB_API_KEY", True),   # True = es un secreto, se oculta
    ("INVEST_DB", False),
]


def config_report() -> list:
    """Cada ajuste con su valor (o su ausencia) y su procedencia."""
    out = []
    for name, secret in REPORTED_SETTINGS:
        raw = setting(name)
        if secret:
            shown = f"puesta ({len(raw)} caracteres)" if raw else "(sin poner)"
        else:
            shown = raw or "(sin poner)"
        out.append({"name": name, "value": shown, "origin": origin(name)})
    return out

# Base de datos de la herramienta personal (perfil, cartera, watchlist, alertas).
DB_PATH = Path(setting("INVEST_DB") or (REPO_ROOT / "personal_invest.db"))

# Base de datos del rastreador STOCK Act ya existente en el repo. Se usa SÓLO
# como señal de contexto opcional; si no existe, no pasa nada.
STOCKACT_DB_PATH = Path(setting("STOCKACT_DB") or (REPO_ROOT / "stockact.db"))

# Caché en disco de respuestas de proveedores (evita golpear las fuentes).
CACHE_DIR = Path(setting("INVEST_CACHE") or (REPO_ROOT / ".data_cache"))

# Contacto para el User-Agent. Las fuentes oficiales (SEC) lo exigen.
CONTACT_EMAIL = setting("INVEST_CONTACT", "usuario-personal@example.com")
USER_AGENT = f"herramienta-inversion-personal/1.0 ({CONTACT_EMAIL})"

# --- Fuentes -------------------------------------------------------------
# Opción B elegida: fuentes sin clave + una clave gratuita opcional.
FINNHUB_API_KEY = setting("FINNHUB_API_KEY").strip()
FINNHUB_ENABLED = bool(FINNHUB_API_KEY)

# Frescura: a partir de estos días, un dato se marca como "viejo" y baja la
# confianza de la recomendación.
STALE_PRICE_DAYS = int(setting("STALE_PRICE_DAYS", "5"))
STALE_FUNDAMENTALS_DAYS = int(setting("STALE_FUNDAMENTALS_DAYS", "200"))

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
    for o in setting(
        "INVEST_CORS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
