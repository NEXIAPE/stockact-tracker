"""
Indicadores calculados sobre precios REALES.

Nada de lo que hay aquí inventa un número: todo se deriva de la serie de
cierres que devuelve el proveedor de precios, y cada resultado se etiqueta con
una fuente derivada que declara el método y la fuente de entrada (ver
``core.datapoint.derived_source``). Un cálculo propio bien declarado no es un
dato inventado.

Todos los indicadores devuelven ``Missing`` cuando no hay historia suficiente,
en vez de rellenar con ceros.
"""

from __future__ import annotations

import math
from datetime import date
from typing import List, Optional, Sequence

from ..providers.stooq import PriceSeries
from .datapoint import DataPoint, Datum, Missing, derived_source

TRADING_DAYS_YEAR = 252


def _sma(values: Sequence[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def last_close(series: PriceSeries) -> DataPoint:
    bar = series.last
    return DataPoint(
        label="Último cierre",
        value=bar.close,
        unit="USD",
        as_of=bar.day,
        source=series.source,
    )


def sma(series: PriceSeries, window: int) -> Datum:
    closes = series.closes()
    value = _sma(closes, window)
    if value is None:
        return Missing(
            label=f"Media móvil de {window} días",
            reason=f"Sólo hay {len(closes)} cierres en la serie; hacen falta {window}.",
            tried=series.source.name,
        )
    return DataPoint(
        label=f"Media móvil de {window} días",
        value=value,
        unit="USD",
        as_of=series.last.day,
        source=derived_source([series.source], f"media aritmética de {window} cierres"),
    )


def pct_vs_sma(series: PriceSeries, window: int) -> Datum:
    avg = sma(series, window)
    if not isinstance(avg, DataPoint):
        return Missing(
            label=f"Distancia a la media de {window} días",
            reason=avg.reason,
            tried=series.source.name,
        )
    close = series.last.close
    pct = (close / avg.value - 1.0) * 100.0
    return DataPoint(
        label=f"Distancia del precio a su media de {window} días",
        value=pct,
        unit="%",
        as_of=series.last.day,
        source=derived_source([series.source], f"(cierre / media {window}d - 1)"),
        precision=1,
    )


def annualized_volatility(series: PriceSeries, window: int = TRADING_DAYS_YEAR) -> Datum:
    closes = series.closes()
    if len(closes) < 60:
        return Missing(
            label="Volatilidad anualizada",
            reason=f"Sólo hay {len(closes)} cierres; hacen falta al menos 60 para que "
                   f"la medida signifique algo.",
            tried=series.source.name,
        )
    window_closes = closes[-(window + 1):]
    returns: List[float] = []
    for prev, cur in zip(window_closes, window_closes[1:]):
        if prev > 0:
            returns.append(cur / prev - 1.0)
    if len(returns) < 30:
        return Missing(
            label="Volatilidad anualizada",
            reason="No hay suficientes rendimientos diarios válidos en la ventana.",
            tried=series.source.name,
        )
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    vol = math.sqrt(variance) * math.sqrt(TRADING_DAYS_YEAR) * 100.0
    return DataPoint(
        label="Volatilidad anualizada (cuánto se mueve el precio)",
        value=vol,
        unit="%",
        as_of=series.last.day,
        source=derived_source(
            [series.source], "desviación típica de rendimientos diarios × √252"
        ),
        precision=1,
    )


def high_52w(series: PriceSeries) -> Datum:
    bars = [b for b in series.bars][-TRADING_DAYS_YEAR:]
    if len(bars) < 30:
        return Missing(
            label="Máximo de 52 semanas",
            reason="Serie demasiado corta para una ventana de 52 semanas.",
            tried=series.source.name,
        )
    best = max(bars, key=lambda b: b.high)
    return DataPoint(
        label="Máximo de 52 semanas",
        value=best.high,
        unit="USD",
        as_of=best.day,
        source=series.source,
    )


def drawdown_from_high(series: PriceSeries) -> Datum:
    peak = high_52w(series)
    if not isinstance(peak, DataPoint) or peak.value <= 0:
        return Missing(
            label="Caída desde el máximo de 52 semanas",
            reason="No hay máximo de 52 semanas fiable.",
            tried=series.source.name,
        )
    close = series.last.close
    dd = (close / peak.value - 1.0) * 100.0
    return DataPoint(
        label="Caída desde el máximo de 52 semanas",
        value=dd,
        unit="%",
        as_of=series.last.day,
        source=derived_source([series.source], "(cierre / máximo 52s - 1)"),
        precision=1,
    )


def total_return(series: PriceSeries, days: int, label: str) -> Datum:
    bars = series.bars
    if len(bars) < days + 1:
        return Missing(
            label=label,
            reason=f"La serie tiene {len(bars)} cierres; hacen falta {days + 1}.",
            tried=series.source.name,
        )
    start = bars[-(days + 1)]
    end = bars[-1]
    if start.close <= 0:
        return Missing(label=label, reason="Precio inicial no válido.", tried=series.source.name)
    pct = (end.close / start.close - 1.0) * 100.0
    return DataPoint(
        label=label,
        value=pct,
        unit="%",
        as_of=end.day,
        source=derived_source([series.source], f"variación de cierre en {days} sesiones"),
        precision=1,
    )


def daily_change(series: PriceSeries) -> Datum:
    bars = series.bars
    if len(bars) < 2 or bars[-2].close <= 0:
        return Missing(
            label="Variación de la última sesión",
            reason="No hay dos cierres consecutivos en la serie.",
            tried=series.source.name,
        )
    pct = (bars[-1].close / bars[-2].close - 1.0) * 100.0
    return DataPoint(
        label="Variación de la última sesión",
        value=pct,
        unit="%",
        as_of=bars[-1].day,
        source=derived_source([series.source], "variación entre los dos últimos cierres"),
        precision=2,
    )


def trend_label(series: PriceSeries) -> str:
    """Describe la tendencia en palabras, sin cifras (las cifras van citadas aparte)."""
    d200 = pct_vs_sma(series, 200)
    d50 = pct_vs_sma(series, 50)
    if isinstance(d200, DataPoint) and isinstance(d50, DataPoint):
        if d200.value > 0 and d50.value > 0:
            return "alcista"
        if d200.value < 0 and d50.value < 0:
            return "bajista"
        return "mixta"
    if isinstance(d200, DataPoint):
        return "alcista" if d200.value > 0 else "bajista"
    return "sin determinar"
