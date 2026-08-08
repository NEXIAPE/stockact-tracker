"""
Persistencia local (SQLite) de la edición personal.

Un solo usuario, un solo archivo, en tu máquina. Tus datos son tuyos: hay
endpoints para exportarlos completos y para borrarlos por completo
(``/api/data/export`` y ``/api/data/wipe``).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import DB_PATH

SCHEMA = """
-- Perfil del inversor. Fila única (id = 1): la herramienta es de un solo usuario.
CREATE TABLE IF NOT EXISTS profile (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    initial_capital     REAL NOT NULL,
    monthly_contribution REAL NOT NULL DEFAULT 0,
    risk_tolerance      TEXT NOT NULL,   -- conservador | moderado | agresivo
    horizon_years       INTEGER NOT NULL,
    goals               TEXT NOT NULL DEFAULT '[]',   -- JSON: lista de objetivos
    experience          TEXT NOT NULL DEFAULT 'principiante',
    base_currency       TEXT NOT NULL DEFAULT 'USD',
    emergency_fund_ok   INTEGER NOT NULL DEFAULT 0,
    notes               TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Posiciones que tienes hoy. Las registras a mano tras operar en tu bróker.
CREATE TABLE IF NOT EXISTS holdings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker         TEXT NOT NULL UNIQUE,
    shares         REAL NOT NULL,
    avg_cost       REAL NOT NULL,          -- coste medio por acción, USD
    asset_type     TEXT NOT NULL DEFAULT 'accion',   -- accion | etf
    opened_at      TEXT,
    notes          TEXT NOT NULL DEFAULT '',
    updated_at     TEXT NOT NULL
);

-- Efectivo disponible sin invertir (fila única).
CREATE TABLE IF NOT EXISTS cash (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    amount      REAL NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);

-- Bitácora manual de operaciones. Sirve de historial; la herramienta NO opera.
CREATE TABLE IF NOT EXISTS trade_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    action      TEXT NOT NULL,    -- compra | venta
    shares      REAL NOT NULL,
    price       REAL NOT NULL,
    traded_on   TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

-- Tickers que sigues, con criterios propios opcionales.
CREATE TABLE IF NOT EXISTS watchlist (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL UNIQUE,
    asset_type          TEXT NOT NULL DEFAULT 'accion',
    reason              TEXT NOT NULL DEFAULT '',
    target_buy_price    REAL,             -- "avísame si baja de X"
    max_drawdown_pct    REAL,             -- "avísame si cae X% desde su máximo de 52s"
    created_at          TEXT NOT NULL
);

-- Alertas generadas. Siempre en tono "vale la pena mirar".
CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint   TEXT NOT NULL UNIQUE,   -- evita repetir la misma alerta
    kind          TEXT NOT NULL,          -- noticia | precio | criterio | cartera
    ticker        TEXT NOT NULL DEFAULT '',
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    evidence      TEXT NOT NULL DEFAULT '[]',  -- JSON: datos citados
    created_at    TEXT NOT NULL,
    read_at       TEXT
);

-- Datos que TÚ lees en una fuente oficial y registras a mano.
-- Existen porque hay cifras (sobre todo de ETFs: ratio de gastos) que ninguna
-- fuente gratuita publica de forma fiable. En vez de que la herramienta se las
-- invente, las lees en la ficha del emisor y quedan citadas con la fecha en que
-- las leíste y el enlace de donde salieron.
CREATE TABLE IF NOT EXISTS user_facts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT NOT NULL,
    key           TEXT NOT NULL,          -- 'expense_ratio', 'dividend_yield', ...
    value         REAL NOT NULL,
    unit          TEXT NOT NULL DEFAULT '%',
    source_label  TEXT NOT NULL DEFAULT 'Ficha oficial del emisor',
    source_url    TEXT NOT NULL DEFAULT '',
    as_of         TEXT NOT NULL,          -- fecha en que leíste el dato
    created_at    TEXT NOT NULL,
    UNIQUE(ticker, key)
);

-- Registro de ejecuciones del briefing (para saber "qué pasó desde la última vez").
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    ran_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_ticker ON trade_log(ticker);
"""

# Tablas que se exportan y se borran con "mis datos son míos".
USER_TABLES = [
    "profile",
    "holdings",
    "cash",
    "trade_log",
    "watchlist",
    "alerts",
    "user_facts",
    "runs",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(path: Optional[Path] = None) -> sqlite3.Connection:
    target = Path(path or DB_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Optional[Path] = None) -> None:
    conn = _connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    conn = _connect(path)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- Utilidades de (de)serialización JSON en columnas de texto -------------
def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def loads(value: str, fallback: Any = None) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback if fallback is not None else []


def export_all(path: Optional[Path] = None) -> dict:
    """Vuelca TODOS tus datos a un dict serializable (para descargar)."""
    with get_conn(path) as conn:
        payload: dict[str, Any] = {
            "exported_at": now_iso(),
            "schema_version": 1,
            "tables": {},
        }
        for table in USER_TABLES:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            payload["tables"][table] = [dict(r) for r in rows]
        return payload


def wipe_all(path: Optional[Path] = None) -> dict:
    """Borra TODOS tus datos. Irreversible: el frontend pide confirmación."""
    deleted: dict[str, int] = {}
    with get_conn(path) as conn:
        for table in USER_TABLES:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            conn.execute(f"DELETE FROM {table}")
            deleted[table] = n
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ({})".format(
            ",".join("?" for _ in USER_TABLES)
        ), USER_TABLES)
    return deleted
