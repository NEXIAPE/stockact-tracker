"""Watchlist: lo que sigues, con los criterios que TÚ fijas para que te avise."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.universe import catalog, etf_dict, guess_asset_type, lookup_etf
from ..db import get_conn, now_iso
from ..schemas import UserFactIn, WatchIn

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY created_at DESC").fetchall()
        facts = conn.execute("SELECT * FROM user_facts").fetchall()

    by_ticker: dict[str, list] = {}
    for f in facts:
        by_ticker.setdefault(f["ticker"].upper(), []).append(
            {
                "key": f["key"],
                "value": f["value"],
                "unit": f["unit"],
                "source_label": f["source_label"],
                "source_url": f["source_url"],
                "as_of": f["as_of"],
            }
        )

    items = []
    for r in rows:
        info = lookup_etf(r["ticker"])
        items.append(
            {
                "id": r["id"],
                "ticker": r["ticker"],
                "asset_type": r["asset_type"],
                "reason": r["reason"],
                "target_buy_price": r["target_buy_price"],
                "max_drawdown_pct": r["max_drawdown_pct"],
                "created_at": r["created_at"],
                "etf_info": etf_dict(info) if info else None,
                "registered_facts": by_ticker.get(r["ticker"].upper(), []),
            }
        )
    return {"items": items}


@router.post("")
def add_watch(payload: WatchIn):
    asset_type = guess_asset_type(payload.ticker, payload.asset_type)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO watchlist (ticker, asset_type, reason, target_buy_price,
                                   max_drawdown_pct, created_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                asset_type = excluded.asset_type,
                reason = excluded.reason,
                target_buy_price = excluded.target_buy_price,
                max_drawdown_pct = excluded.max_drawdown_pct
            """,
            (
                payload.ticker,
                asset_type,
                payload.reason,
                payload.target_buy_price,
                payload.max_drawdown_pct,
                now_iso(),
            ),
        )
    return {"ok": True, "ticker": payload.ticker}


@router.delete("/{ticker}")
def remove_watch(ticker: str):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.strip().upper(),))
        if cur.rowcount == 0:
            raise HTTPException(404, f"{ticker.upper()} no está en tu watchlist.")
    return {"ok": True}


@router.post("/{ticker}/facts")
def register_fact(ticker: str, payload: UserFactIn):
    """Registra un dato que leíste en una fuente oficial (p. ej. el ratio de gastos).

    Existe porque hay cifras que ninguna fuente gratuita publica de forma fiable.
    La alternativa sería que la herramienta se las inventara de memoria, y eso
    está prohibido. Registrándolo tú, el dato queda citado con su fuente, su
    enlace y la fecha en que lo leíste.
    """
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_facts (ticker, key, value, unit, source_label, source_url,
                                    as_of, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker, key) DO UPDATE SET
                value = excluded.value,
                unit = excluded.unit,
                source_label = excluded.source_label,
                source_url = excluded.source_url,
                as_of = excluded.as_of,
                created_at = excluded.created_at
            """,
            (
                ticker.strip().upper(),
                payload.key,
                payload.value,
                payload.unit,
                payload.source_label,
                payload.source_url,
                payload.as_of.isoformat(),
                now_iso(),
            ),
        )
    return {"ok": True, "ticker": ticker.strip().upper(), "key": payload.key}


@router.delete("/{ticker}/facts/{key}")
def delete_fact(ticker: str, key: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM user_facts WHERE UPPER(ticker) = ? AND key = ?",
            (ticker.strip().upper(), key.strip().lower()),
        )
    return {"ok": True}


@router.get("/catalog/etfs")
def etf_catalog():
    """Catálogo de referencia de ETFs. Sin cifras: sólo hechos cualitativos y el
    enlace a la ficha oficial, porque los ratios de gastos cambian y escribirlos
    a mano en el código sería inventar datos."""
    return {
        "etfs": catalog(),
        "note": (
            "Esta lista es un punto de partida para investigar, no una recomendación. "
            "Las comisiones y la composición de cada fondo están en la ficha oficial "
            "del emisor: consúltalas ahí y regístralas si quieres que aparezcan citadas."
        ),
    }
