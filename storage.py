"""
Persistencia en SQLite con detección incremental de novedades.

Cada divulgación se identifica por su ``transaction_key`` (clave de negocio).
Al guardar un lote, sólo se insertan las que no estaban ya en la base; esas son
las "novedades" del día. Así el informe diario puede destacar lo nuevo sin
volver a reportar lo de ayer.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import List

from models import Disclosure


DEFAULT_DB = "stockact.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS disclosures (
    id                 TEXT PRIMARY KEY,
    source             TEXT,
    doc_id             TEXT,
    filer_name         TEXT,
    ticker             TEXT,
    asset_description  TEXT,
    transaction_type   TEXT,
    transaction_date   TEXT,
    notification_date  TEXT,
    amount_range       TEXT,
    amount_low         REAL,
    amount_high        REAL,
    is_amendment       INTEGER,
    amends_doc_id      TEXT,
    sector             TEXT,
    first_seen         TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON disclosures(transaction_date);
CREATE INDEX IF NOT EXISTS idx_ticker ON disclosures(ticker);
"""


class Storage:
    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- Inserción incremental --------------------------------------------
    def save_new(self, disclosures: List[Disclosure]) -> List[Disclosure]:
        """Inserta las divulgaciones no vistas. Devuelve sólo las nuevas."""
        new_items: List[Disclosure] = []
        now = datetime.utcnow().isoformat(timespec="seconds")
        cur = self.conn.cursor()
        for d in disclosures:
            row_id = d.transaction_key()
            cur.execute("SELECT 1 FROM disclosures WHERE id = ?", (row_id,))
            if cur.fetchone() is not None:
                continue  # ya existía -> no es novedad
            r = d.to_row()
            cur.execute(
                """
                INSERT INTO disclosures (
                    id, source, doc_id, filer_name, ticker, asset_description,
                    transaction_type, transaction_date, notification_date,
                    amount_range, amount_low, amount_high, is_amendment,
                    amends_doc_id, sector, first_seen
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row_id, r["source"], r["doc_id"], r["filer_name"], r["ticker"],
                    r["asset_description"], r["transaction_type"],
                    r["transaction_date"], r["notification_date"], r["amount_range"],
                    r["amount_low"], r["amount_high"], 1 if r["is_amendment"] else 0,
                    r["amends_doc_id"], r["sector"], now,
                ),
            )
            new_items.append(d)
        self.conn.commit()
        return new_items

    # -- Consultas para el informe ----------------------------------------
    def top_tickers(self, days: int = 30, limit: int = 10, today: date | None = None):
        """Top tickers por nº de transacciones en los últimos ``days`` días.

        Se mide por ``transaction_date`` (fecha de la operación).
        """
        today = today or date.today()
        since = (today - timedelta(days=days)).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT ticker, COUNT(*) AS n
            FROM disclosures
            WHERE ticker <> '' AND transaction_date >= ?
            GROUP BY ticker
            ORDER BY n DESC, ticker ASC
            LIMIT ?
            """,
            (since, limit),
        )
        return [(row["ticker"], row["n"]) for row in cur.fetchall()]

    def sector_breakdown(self, days: int = 30, today: date | None = None):
        """Desglose por sector (nº de transacciones) en los últimos ``days``."""
        today = today or date.today()
        since = (today - timedelta(days=days)).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT sector, COUNT(*) AS n
            FROM disclosures
            WHERE transaction_date >= ?
            GROUP BY sector
            ORDER BY n DESC, sector ASC
            """,
            (since,),
        )
        return [(row["sector"], row["n"]) for row in cur.fetchall()]

    def total_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM disclosures")
        return cur.fetchone()["n"]
