"""
Señal de contexto: divulgaciones del STOCK Act (rastreador ya existente en este repo).

Reutiliza ``stockact.db``, la base que genera el CLI original. Si el archivo no
existe (porque nunca has corrido el rastreador), este proveedor devuelve "sin
datos" y no pasa nada.

POR QUÉ TIENE PESO CERO EN LA DECISIÓN
--------------------------------------
Los Periodic Transaction Reports pueden presentarse hasta ~45 días DESPUÉS de
la operación. Lo que ves hoy describe el pasado, a veces un pasado de mes y
medio. Es contexto interesante ("hubo actividad divulgada en este ticker"),
nunca una razón para comprar o vender. El motor de recomendación lo muestra
como dato de color y no lo suma al score.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from ..config import STOCKACT_DB_PATH
from ..core.datapoint import Source

DISCLOSURE_LAG_NOTICE = (
    "Las divulgaciones del STOCK Act pueden presentarse hasta ~45 días después de "
    "la operación. Describen el pasado, no el presente, y no son una señal de "
    "compra ni de venta."
)


@dataclass(frozen=True)
class DisclosureSignal:
    ticker: str
    purchases: int
    sales: int
    most_recent_transaction: Optional[date]
    window_days: int
    source: Source

    @property
    def total(self) -> int:
        return self.purchases + self.sales

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "purchases": self.purchases,
            "sales": self.sales,
            "total": self.total,
            "most_recent_transaction": (
                self.most_recent_transaction.isoformat()
                if self.most_recent_transaction
                else None
            ),
            "window_days": self.window_days,
            "source_name": self.source.name,
            "weight_in_recommendation": "cero (sólo contexto)",
            "caveat": DISCLOSURE_LAG_NOTICE,
        }


def available() -> bool:
    return STOCKACT_DB_PATH.exists()


def fetch_signal(ticker: str, window_days: int = 180) -> Optional[DisclosureSignal]:
    """Cuenta divulgaciones recientes de un ticker. ``None`` si no hay base."""
    if not available():
        return None

    since = (date.today() - timedelta(days=window_days)).isoformat()
    try:
        conn = sqlite3.connect(f"file:{STOCKACT_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return None

    try:
        rows = conn.execute(
            """
            SELECT transaction_type, transaction_date
            FROM disclosures
            WHERE UPPER(ticker) = ? AND transaction_date >= ?
            """,
            (ticker.strip().upper(), since),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    if not rows:
        return None

    purchases = sum(1 for r in rows if r["transaction_type"] == "purchase")
    sales = sum(1 for r in rows if r["transaction_type"] == "sale")
    dates = sorted(r["transaction_date"] for r in rows if r["transaction_date"])
    most_recent = None
    if dates:
        try:
            most_recent = date.fromisoformat(dates[-1])
        except ValueError:
            most_recent = None

    return DisclosureSignal(
        ticker=ticker.upper(),
        purchases=purchases,
        sales=sales,
        most_recent_transaction=most_recent,
        window_days=window_days,
        source=Source(
            name="Rastreador STOCK Act local (divulgaciones públicas del Congreso EE. UU.)",
            url="https://disclosures-clerk.house.gov/",
        ),
    )


def top_recent(limit: int = 10, window_days: int = 90) -> List[dict]:
    if not available():
        return []
    since = (date.today() - timedelta(days=window_days)).isoformat()
    try:
        conn = sqlite3.connect(f"file:{STOCKACT_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT ticker, COUNT(*) AS n
            FROM disclosures
            WHERE ticker <> '' AND transaction_date >= ?
            GROUP BY ticker ORDER BY n DESC, ticker ASC LIMIT ?
            """,
            (since, limit),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return []
    return [{"ticker": r["ticker"], "disclosures": r["n"]} for r in rows]
