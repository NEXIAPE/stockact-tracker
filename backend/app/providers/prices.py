"""
Fuente de precios con respaldo automático.

El precio es el único dato sin el cual la herramienta no puede opinar. Depender
de un solo proveedor gratuito significaba que una caída — o una red desde la que
ese proveedor no es accesible — dejaba la herramienta inservible. Esto prueba
varios en orden y se queda con el primero que responda.

Honestidad, que aquí importa especialmente: la serie devuelta cita SIEMPRE al
proveedor que realmente sirvió el dato, no al que se intentó primero. Si el
precio vino de Yahoo, en la pantalla pone Yahoo.

Orden por defecto: Stooq y luego Yahoo. Se puede cambiar con la variable de
entorno ``PRICE_PROVIDERS`` (lista separada por comas), por ejemplo:

    PRICE_PROVIDERS=yahoo,stooq      # si Stooq no es accesible desde tu red
    PRICE_PROVIDERS=yahoo            # usar sólo Yahoo
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from ..config import setting
from .http import FetchError
from .series import Bar, PriceSeries  # noqa: F401  (re-exportados por comodidad)
from . import stooq, yahoo_chart

Fetcher = Callable[..., PriceSeries]

PROVIDERS: Dict[str, Tuple[str, Fetcher]] = {
    "stooq": ("Stooq", stooq.fetch_daily),
    "yahoo": ("Yahoo Finance", yahoo_chart.fetch_daily),
}

DEFAULT_ORDER = ["stooq", "yahoo"]


def order() -> List[str]:
    raw = setting("PRICE_PROVIDERS").strip()
    if not raw:
        return list(DEFAULT_ORDER)
    chosen = [p.strip().lower() for p in raw.split(",") if p.strip().lower() in PROVIDERS]
    return chosen or list(DEFAULT_ORDER)


def fetch_daily(ticker: str, ttl: Optional[int] = None) -> PriceSeries:
    """Primer proveedor que responda. Si fallan todos, lo dice y enumera por qué."""
    problems: List[str] = []

    for key in order():
        label, fetcher = PROVIDERS[key]
        try:
            return fetcher(ticker, ttl=ttl)
        except FetchError as exc:
            problems.append(f"{label}: {exc}")
        except Exception as exc:  # un parser roto no debe tumbar al siguiente
            problems.append(f"{label}: error inesperado ({exc})")

    raise FetchError(
        f"Ningún proveedor de precios pudo servir {ticker.upper()}. "
        + " | ".join(problems)
    )


def probe(ticker: str) -> List[dict]:
    """Prueba TODOS los proveedores y reporta cada uno. Sólo para diagnóstico."""
    out: List[dict] = []
    for key in order():
        label, fetcher = PROVIDERS[key]
        try:
            series = fetcher(ticker)
            out.append({
                "key": key,
                "name": label,
                "ok": True,
                "bars": len(series.bars),
                "last_day": series.last.day,
                "last_close": series.last.close,
                "source": series.source.name,
                "error": "",
            })
        except Exception as exc:
            out.append({
                "key": key, "name": label, "ok": False, "bars": 0,
                "last_day": None, "last_close": None, "source": "", "error": str(exc),
            })
    return out
