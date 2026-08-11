"""
Finnhub — fuente OPCIONAL con clave gratuita (opción B que elegiste).

Sin ``FINNHUB_API_KEY`` en el entorno, este proveedor se desactiva solo y la
herramienta funciona igual con las fuentes sin clave (Stooq + SEC EDGAR + RSS).
Con clave añade tres cosas que las fuentes gratuitas no dan bien:

  * cotización más fresca que el cierre diario de Stooq,
  * ratios ya calculados (PER, márgenes, deuda) incluidos ETFs parcialmente,
  * noticias por ticker con fecha exacta.

Cómo activarlo:
    export FINNHUB_API_KEY="tu_clave"        # se obtiene gratis en finnhub.io

Los límites del plan gratuito los fija Finnhub y pueden cambiar; si te devuelve
error por cuota, la herramienta lo dice y cae a las fuentes sin clave en vez de
inventarse el dato.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from ..config import CACHE_TTL, FINNHUB_API_KEY, FINNHUB_ENABLED
from ..core.datapoint import DataPoint, Source
from .http import FetchError, client

BASE = "https://finnhub.io/api/v1"
WEB = "https://finnhub.io/"


def enabled() -> bool:
    return FINNHUB_ENABLED


def _get(path: str, params: Dict[str, str], ttl: int) -> Optional[dict]:
    if not enabled():
        return None
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}?{query}&token={FINNHUB_API_KEY}"
    # La clave nunca entra en la clave de caché (no se escribe en disco).
    cache_key = f"finnhub:{path}?{query}"
    try:
        raw = client().get(url, ttl=ttl, cache_key=cache_key)
        return json.loads(raw.decode("utf-8", "replace"))
    except (FetchError, ValueError):
        return None


@dataclass(frozen=True)
class Quote:
    price: float
    change_pct: float
    day: date


def fetch_quote(ticker: str) -> Optional[DataPoint]:
    """Cotización más reciente. ``None`` si no hay clave o falla la fuente."""
    data = _get("/quote", {"symbol": ticker.upper()}, CACHE_TTL["quote"])
    if not data or not data.get("c"):
        return None
    ts = data.get("t")
    try:
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).date() if ts else date.today()
    except (ValueError, OSError, TypeError):
        day = date.today()
    return DataPoint(
        label="Cotización",
        value=float(data["c"]),
        unit="USD",
        as_of=day,
        source=Source(name="Finnhub (cotización)", url=WEB),
    )


# Métricas de Finnhub que sabemos leer, con su etiqueta y unidad.
_METRICS = {
    "peBasicExclExtraTTM": ("PER (precio / beneficio, 12 meses)", "x", 1),
    "peNormalizedAnnual": ("PER normalizado (anual)", "x", 1),
    "netProfitMarginTTM": ("Margen neto (12 meses)", "%", 1),
    "totalDebt/totalEquityQuarterly": ("Deuda / patrimonio", "x", 2),
    "dividendYieldIndicatedAnnual": ("Rentabilidad por dividendo", "%", 2),
    "52WeekHigh": ("Máximo de 52 semanas", "USD", 2),
    "52WeekLow": ("Mínimo de 52 semanas", "USD", 2),
    "beta": ("Beta (sensibilidad al mercado)", "x", 2),
    "revenueGrowthTTMYoy": ("Crecimiento de ingresos (12m, interanual)", "%", 1),
}


def fetch_metrics(ticker: str) -> Dict[str, DataPoint]:
    """Ratios ya calculados. Diccionario vacío si no hay clave o no hay datos."""
    data = _get("/stock/metric", {"symbol": ticker.upper(), "metric": "all"}, CACHE_TTL["metrics"])
    if not data:
        return {}
    metric = data.get("metric") or {}
    source = Source(name="Finnhub (métricas)", url=WEB)
    today = date.today()

    out: Dict[str, DataPoint] = {}
    for key, (label, unit, precision) in _METRICS.items():
        value = metric.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        out[key] = DataPoint(
            label=label,
            value=numeric,
            unit=unit,
            # Finnhub no expone la fecha de corte por métrica; se cita la fecha
            # de consulta y se dice explícitamente que es así.
            as_of=today,
            source=source,
            precision=precision,
        )
    return out


def fetch_company_news(ticker: str, days: int = 7, limit: int = 10) -> List[dict]:
    today = date.today()
    since = today - timedelta(days=days)
    data = _get(
        "/company-news",
        {"symbol": ticker.upper(), "from": since.isoformat(), "to": today.isoformat()},
        CACHE_TTL["news"],
    )
    if not isinstance(data, list):
        return []
    items: List[dict] = []
    for entry in data[:limit]:
        ts = entry.get("datetime")
        try:
            published = datetime.fromtimestamp(int(ts), tz=timezone.utc).date() if ts else None
        except (ValueError, OSError, TypeError):
            published = None
        items.append(
            {
                "title": entry.get("headline", ""),
                "url": entry.get("url", ""),
                "published": published.isoformat() if published else None,
                "source_name": f"Finnhub / {entry.get('source', 'desconocido')}",
                "kind": "prensa",
                "summary": (entry.get("summary") or "")[:280],
                "interpretation_notice": (
                    "Titular de terceros. Es INTERPRETACIÓN del mercado, no un hecho "
                    "sobre el valor del activo."
                ),
            }
        )
    return items
