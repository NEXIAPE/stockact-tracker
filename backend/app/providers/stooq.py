"""
Precios de cierre diario desde Stooq (gratis, sin API key).

Stooq publica series históricas en CSV. Cubre acciones y ETFs de EE. UU. con
el sufijo ``.us``. Es un cierre diario: NO hay intradía. Para un horizonte de
inversión largo (que es el que corresponde a un perfil principiante) es
suficiente, y la herramienta siempre muestra la fecha del último cierre para
que sepas exactamente de cuándo es el dato.

Limitación honesta: Stooq no ofrece garantía de servicio ni SLA. Si falla, la
herramienta lo dice ("no pude obtener el precio"); nunca inventa un valor.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import List, Optional

from ..config import CACHE_TTL
from ..core.datapoint import Source
from .http import FetchError, client
# Bar y PriceSeries viven en series.py para que varios proveedores compartan el
# mismo formato. Se re-exportan aquí por compatibilidad con importaciones previas.
from .series import Bar, PriceSeries  # noqa: F401

BASE = "https://stooq.com/q/d/l/"
WEB = "https://stooq.com/q/d/?s={sym}"


def _symbol(ticker: str) -> str:
    t = ticker.strip().lower().replace(".", "-")
    return f"{t}.us"


def fetch_daily(ticker: str, ttl: Optional[int] = None) -> PriceSeries:
    """Serie de cierres diarios. Lanza ``FetchError`` si no hay datos."""
    sym = _symbol(ticker)
    url = f"{BASE}?s={sym}&i=d"
    raw = client().get(url, ttl=ttl if ttl is not None else CACHE_TTL["prices"])
    text = raw.decode("utf-8", "replace").strip()

    if not text or text.lower().startswith("no data") or "\n" not in text:
        raise FetchError(
            f"Stooq no devolvió datos para {ticker.upper()}. Puede que el símbolo "
            f"no exista o no esté cubierto."
        )

    bars: List[Bar] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            bars.append(
                Bar(
                    day=datetime.strptime(row["Date"], "%Y-%m-%d").date(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume") or 0),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue  # fila corrupta: se ignora, no se inventa

    if not bars:
        raise FetchError(f"Stooq devolvió una serie vacía para {ticker.upper()}.")

    bars.sort(key=lambda b: b.day)
    return PriceSeries(
        ticker=ticker.upper(),
        bars=bars,
        source=Source(name="Stooq (cierre diario)", url=WEB.format(sym=sym)),
    )
