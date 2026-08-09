"""
Formato común de una serie de precios.

Vive en su propio módulo para que varios proveedores (Stooq, Yahoo) puedan
producir exactamente la misma estructura sin depender unos de otros, y para que
las capas superiores no sepan ni les importe de dónde salió el precio — más allá
de la cita, que siempre viaja con el dato.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from ..core.datapoint import Source


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class PriceSeries:
    ticker: str
    bars: List[Bar]
    source: Source

    @property
    def last(self) -> Bar:
        return self.bars[-1]

    def closes(self) -> List[float]:
        return [b.close for b in self.bars]
