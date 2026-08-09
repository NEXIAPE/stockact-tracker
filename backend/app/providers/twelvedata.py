"""
Twelve Data — tercer proveedor de precios, OPCIONAL y con clave gratuita.

Sin ``TWELVEDATA_API_KEY`` en la configuración se desactiva solo y no estorba.

POR QUÉ EXISTE, CON HONESTIDAD
------------------------------
Lo pediste, y está bien tenerlo, pero conviene ser claro: hoy no resuelve
ningún problema que tengas. Ya hay dos proveedores de precios y uno de ellos te
funciona. Esto es una red de seguridad para el día en que Yahoo cambie su
endpoint no oficial — que puede pasar sin aviso — o Stooq siga inaccesible.

A cambio de esa red pagas mantenimiento: una clave más que rotar y un formato
más que puede cambiar. Por eso queda el ÚLTIMO en el orden por defecto: sólo se
usa si los dos anteriores fallan, y así su cuota diaria no se gasta en vano.

El plan gratuito ronda las 800 peticiones al día y 8 por minuto, según Twelve
Data; los límites los fija el proveedor y pueden cambiar. Si se agota la cuota,
la herramienta lo dice y pasa al siguiente en vez de inventar el dato.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from ..config import CACHE_TTL, setting
from ..core.datapoint import Source
from .http import FetchError, client
from .series import Bar, PriceSeries

BASE = "https://api.twelvedata.com/time_series"
WEB = "https://twelvedata.com/"


def api_key() -> str:
    return setting("TWELVEDATA_API_KEY").strip()


def enabled() -> bool:
    return bool(api_key())


def fetch_daily(ticker: str, ttl: Optional[int] = None) -> PriceSeries:
    key = api_key()
    if not key:
        raise FetchError(
            "Twelve Data no está configurado (falta TWELVEDATA_API_KEY). Es opcional: "
            "la herramienta funciona con los otros proveedores de precios."
        )

    symbol = ticker.strip().upper()
    query = f"symbol={symbol}&interval=1day&outputsize=800&format=JSON"
    url = f"{BASE}?{query}&apikey={key}"
    # La clave nunca entra en el nombre del archivo de caché.
    cache_key = f"twelvedata:{query}"

    raw = client().get(
        url, ttl=ttl if ttl is not None else CACHE_TTL["prices"], cache_key=cache_key
    )
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise FetchError(f"Twelve Data devolvió algo que no es JSON para {symbol}.") from exc

    # Los errores llegan con status "error" y HTTP 200, así que hay que mirarlos.
    if isinstance(payload, dict) and payload.get("status") == "error":
        raise FetchError(
            f"Twelve Data rechazó {symbol}: {payload.get('message', 'sin detalle')}"
        )

    values = payload.get("values") if isinstance(payload, dict) else None
    if not values:
        raise FetchError(f"Twelve Data no devolvió datos para {symbol}.")

    bars: List[Bar] = []
    for row in values:
        try:
            close = float(row["close"])
            day = datetime.strptime(row["datetime"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError, TypeError):
            continue  # fila ilegible: se descarta, no se rellena

        def num(field: str, fallback: float) -> float:
            try:
                return float(row[field])
            except (KeyError, ValueError, TypeError):
                return fallback

        bars.append(Bar(
            day=day,
            open=num("open", close),
            high=num("high", close),
            low=num("low", close),
            close=close,
            volume=num("volume", 0.0),
        ))

    if not bars:
        raise FetchError(f"Twelve Data devolvió una serie vacía para {symbol}.")

    bars.sort(key=lambda b: b.day)
    return PriceSeries(
        ticker=symbol,
        bars=bars,
        source=Source(name="Twelve Data (cierre diario)", url=WEB),
    )
