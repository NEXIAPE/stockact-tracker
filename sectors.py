"""
Clasificación sencilla de tickers a sectores.

Es deliberadamente offline y estática: un mapa ticker -> sector más un par de
heurísticas. No consulta servicios externos para que el --self-test sea 100%
reproducible y para no añadir dependencias ni más rate limits.

Para producción puedes reemplazar/extender ``lookup_sector`` con una fuente
real (p. ej. un dataset descargado, o un proveedor con su propia licencia).
"""

from __future__ import annotations

# Mapa mínimo de ejemplo. Amplíalo según necesites.
_TICKER_SECTOR = {
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "NVDA": "Information Technology",
    "GOOGL": "Communication Services",
    "GOOG": "Communication Services",
    "META": "Communication Services",
    "NFLX": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "JPM": "Financials",
    "BAC": "Financials",
    "GS": "Financials",
    "BRK.B": "Financials",
    "JNJ": "Health Care",
    "PFE": "Health Care",
    "UNH": "Health Care",
    "LLY": "Health Care",
    "XOM": "Energy",
    "CVX": "Energy",
    "COP": "Energy",
    "BA": "Industrials",
    "CAT": "Industrials",
    "GE": "Industrials",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "PEP": "Consumer Staples",
    "WMT": "Consumer Staples",
    "NEE": "Utilities",
    "DUK": "Utilities",
    "AMT": "Real Estate",
    "PLD": "Real Estate",
    "LIN": "Materials",
    "FCX": "Materials",
}

UNKNOWN_SECTOR = "Unknown"


def lookup_sector(ticker: str) -> str:
    """Devuelve el sector GICS-aproximado para un ticker, o 'Unknown'."""
    if not ticker:
        return UNKNOWN_SECTOR
    return _TICKER_SECTOR.get(ticker.strip().upper(), UNKNOWN_SECTOR)
