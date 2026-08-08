"""Cartera: posiciones, efectivo y bitácora de operaciones ya ejecutadas por ti."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.portfolio import load_portfolio, portfolio_dict
from ..core.universe import guess_asset_type
from ..db import get_conn, now_iso
from ..deps import load_profile
from ..core.profile import derive_strategy
from ..schemas import CashIn, HoldingIn, TradeIn

router = APIRouter(prefix="/api/portfolio", tags=["cartera"])


@router.get("")
def get_portfolio():
    """Tu cartera valorada con precios reales, más los desvíos frente a tu estrategia."""
    with get_conn() as conn:
        profile = load_profile(conn)
        strategy = derive_strategy(profile) if profile else None
        state = load_portfolio(conn)
        return portfolio_dict(state, profile, strategy)


@router.put("/holdings")
def upsert_holding(payload: HoldingIn):
    """Registra o actualiza una posición. Es un registro de lo que YA tienes."""
    asset_type = guess_asset_type(payload.ticker, payload.asset_type)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO holdings (ticker, shares, avg_cost, asset_type, notes, updated_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                shares = excluded.shares,
                avg_cost = excluded.avg_cost,
                asset_type = excluded.asset_type,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                payload.ticker,
                payload.shares,
                payload.avg_cost,
                asset_type,
                payload.notes,
                now_iso(),
            ),
        )
    return {"ok": True, "ticker": payload.ticker}


@router.delete("/holdings/{ticker}")
def delete_holding(ticker: str):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.strip().upper(),))
        if cur.rowcount == 0:
            raise HTTPException(404, f"No tienes {ticker.upper()} registrado.")
    return {"ok": True, "deleted": ticker.strip().upper()}


@router.put("/cash")
def set_cash(payload: CashIn):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cash (id, amount, updated_at) VALUES (1,?,?)
            ON CONFLICT(id) DO UPDATE SET amount = excluded.amount, updated_at = excluded.updated_at
            """,
            (payload.amount, now_iso()),
        )
    return {"ok": True, "amount": payload.amount}


@router.get("/trades")
def list_trades(limit: int = 100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trade_log ORDER BY traded_on DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"trades": [dict(r) for r in rows]}


@router.post("/trades")
def add_trade(payload: TradeIn):
    """Anota una operación que YA hiciste en tu bróker.

    Esto no ejecuta nada: es tu bitácora. La herramienta no tiene ninguna
    conexión con ningún bróker.
    """
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO trade_log (ticker, action, shares, price, traded_on, notes, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                payload.ticker,
                payload.action,
                payload.shares,
                payload.price,
                payload.traded_on.isoformat(),
                payload.notes,
                now_iso(),
            ),
        )
    return {
        "ok": True,
        "note": (
            "Registrado en tu bitácora. Recuerda actualizar también la posición y el efectivo "
            "para que la valoración cuadre."
        ),
    }


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM trade_log WHERE id = ?", (trade_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Esa operación no está en tu bitácora.")
    return {"ok": True}
