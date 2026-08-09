"""
Precios de cierre diario desde Yahoo Finance (gratis, sin API key).

Existe como ALTERNATIVA a Stooq. Stooq no está disponible desde todas las redes
(hay proveedores y países desde los que devuelve 403), y sin precios la
herramienta no puede analizar nada. Tener dos fuentes independientes para el
dato más crítico evita que una sola caída deje la herramienta inservible.

Limitaciones honestas, iguales o peores que las de Stooq:

  * Es un endpoint NO OFICIAL. Yahoo no lo documenta ni garantiza nada, y puede
    cambiarlo o cerrarlo sin aviso. Por eso no es la fuente principal.
  * Devuelve cierres diarios, no intradía real para histórico.
  * Puede traer huecos (días sin datos): esas sesiones se descartan en vez de
    rellenarse, porque inventar un precio sería peor que no tenerlo.

Se usa el cierre AJUSTADO cuando está disponible: corrige splits y dividendos,
que si no distorsionarían las medias móviles y la variación a un año.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import List, Optional

from ..config import CACHE_TTL
from ..core.datapoint import Source
from .http import FetchError, client
from .series import Bar, PriceSeries

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
WEB = "https://finance.yahoo.com/quote/{symbol}"

# Yahoo rechaza clientes sin User-Agent de navegador en este endpoint.
BROWSERISH = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _symbol(ticker: str) -> str:
    # Yahoo usa guion donde otros usan punto: BRK.B -> BRK-B
    return ticker.strip().upper().replace(".", "-")


def fetch_daily(ticker: str, ttl: Optional[int] = None) -> PriceSeries:
    """Serie de cierres diarios de los últimos dos años."""
    sym = _symbol(ticker)
    url = f"{CHART.format(symbol=sym)}?range=2y&interval=1d"

    raw = client().get(
        url,
        ttl=ttl if ttl is not None else CACHE_TTL["prices"],
        headers={"User-Agent": BROWSERISH, "Accept": "application/json"},
    )

    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise FetchError(f"Yahoo devolvió algo que no es JSON para {ticker.upper()}.") from exc

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise FetchError(f"Yahoo rechazó {ticker.upper()}: {chart['error']}")

    results = chart.get("result") or []
    if not results:
        raise FetchError(
            f"Yahoo no devolvió datos para {ticker.upper()}. Puede que el símbolo no exista."
        )

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote_blocks = (result.get("indicators") or {}).get("quote") or [{}]
    quote = quote_blocks[0] if quote_blocks else {}

    # El cierre ajustado corrige splits y dividendos; se prefiere si existe.
    adj_blocks = (result.get("indicators") or {}).get("adjclose") or []
    adjclose = (adj_blocks[0].get("adjclose") if adj_blocks else None) or []

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    bars: List[Bar] = []
    for i, ts in enumerate(timestamps):
        close = None
        if i < len(adjclose) and adjclose[i] is not None:
            close = adjclose[i]
        elif i < len(closes) and closes[i] is not None:
            close = closes[i]
        if close is None or ts is None:
            continue  # hueco: se descarta, no se rellena

        def at(seq, fallback):
            value = seq[i] if i < len(seq) else None
            return float(value) if value is not None else float(fallback)

        try:
            day = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
            bars.append(
                Bar(
                    day=day,
                    open=at(opens, close),
                    high=at(highs, close),
                    low=at(lows, close),
                    close=float(close),
                    volume=at(volumes, 0),
                )
            )
        except (ValueError, OSError, TypeError):
            continue

    if not bars:
        raise FetchError(f"Yahoo devolvió una serie vacía para {ticker.upper()}.")

    bars.sort(key=lambda b: b.day)
    return PriceSeries(
        ticker=ticker.upper(),
        bars=bars,
        source=Source(
            name="Yahoo Finance (cierre diario ajustado)",
            url=WEB.format(symbol=sym),
        ),
    )
