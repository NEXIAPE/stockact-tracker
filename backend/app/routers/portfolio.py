"""Cartera: posiciones, efectivo y bitácora de operaciones ya ejecutadas por ti."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from ..core.portfolio import load_portfolio, portfolio_dict
from ..core.universe import guess_asset_type
from ..db import get_conn, now_iso
from ..deps import load_profile
from ..core.profile import derive_strategy
from ..core import performance as perf_mod
from ..core import thesis as thesis_mod
from ..schemas import CashIn, HoldingIn, ThesisIn, TradeIn

router = APIRouter(prefix="/api/portfolio", tags=["cartera"])


@router.get("")
def get_portfolio(with_prices: bool = True):
    """Tu cartera valorada con precios reales, más los desvíos frente a tu estrategia.

    Con ``with_prices=false`` devuelve solo lo guardado —participaciones, coste
    medio, efectivo— sin tocar la red. La pantalla lo pide así primero para
    poder mostrarte lo tuyo de inmediato, y vuelve a pedirlo ya valorado.
    """
    with get_conn() as conn:
        profile = load_profile(conn)
        strategy = derive_strategy(profile) if profile else None
        state = load_portfolio(conn, with_prices=with_prices)
        return portfolio_dict(state, profile, strategy)


@router.put("/holdings")
def upsert_holding(payload: HoldingIn):
    """Registra o actualiza una posición. Es un registro de lo que YA tienes."""
    asset_type = guess_asset_type(payload.ticker, payload.asset_type)
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT thesis, invalidation FROM holdings WHERE ticker = ?", (payload.ticker,)
        ).fetchone()
        # Actualizar una posición sin volver a escribir la tesis no debe borrarla.
        thesis_text = payload.thesis or (existing["thesis"] if existing else "")
        invalidation = payload.invalidation or (existing["invalidation"] if existing else "")
        reviewed = date.today().isoformat() if (payload.thesis or payload.invalidation) else None

        conn.execute(
            """
            INSERT INTO holdings (ticker, shares, avg_cost, asset_type, notes,
                                  thesis, invalidation, thesis_reviewed_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                shares = excluded.shares,
                avg_cost = excluded.avg_cost,
                asset_type = excluded.asset_type,
                notes = excluded.notes,
                thesis = excluded.thesis,
                invalidation = excluded.invalidation,
                thesis_reviewed_at = COALESCE(excluded.thesis_reviewed_at,
                                              holdings.thesis_reviewed_at),
                updated_at = excluded.updated_at
            """,
            (
                payload.ticker,
                payload.shares,
                payload.avg_cost,
                asset_type,
                payload.notes,
                thesis_text,
                invalidation,
                reviewed,
                now_iso(),
            ),
        )
    return {
        "ok": True,
        "ticker": payload.ticker,
        "thesis_missing": not thesis_text.strip(),
        "note": (
            "No anotaste por qué compraste esto. Sin esa nota, lo único que puedo mirar "
            "para opinar sobre vender es el precio, que es la peor señal posible."
        ) if not thesis_text.strip() else "",
    }


@router.get("/performance")
def performance(benchmark: str = perf_mod.DEFAULT_BENCHMARK):
    """Cómo te va de verdad, comparado con haber comprado un fondo amplio."""
    with get_conn() as conn:
        state = load_portfolio(conn)
        resultado = perf_mod.compute(conn, state, benchmark=benchmark)
    return perf_mod.to_dict(resultado)


@router.get("/thesis")
def list_theses():
    """Tu tesis de cada posición, y cuáles faltan o llevan mucho sin revisar."""
    with get_conn() as conn:
        todas = thesis_mod.load_all(conn)
    return {
        "theses": [t.to_dict() for t in todas],
        "missing_warning": thesis_mod.missing_thesis_warning(todas),
        "stale_warning": thesis_mod.stale_thesis_warning(todas),
        "why_it_matters": (
            "La razón por la que compraste algo es la única señal de venta que vale. "
            "Que el precio baje no significa que esa razón haya dejado de ser cierta."
        ),
    }


@router.put("/holdings/{ticker}/thesis")
def save_thesis(ticker: str, payload: ThesisIn):
    """Anota o revisa por qué tienes esta posición."""
    ticker = ticker.strip().upper()
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM holdings WHERE ticker = ?", (ticker,)).fetchone()
        if not exists:
            raise HTTPException(404, f"No tienes {ticker} registrado.")
        conn.execute(
            """
            UPDATE holdings SET thesis = ?, invalidation = ?, thesis_reviewed_at = ?,
                                updated_at = ?
            WHERE ticker = ?
            """,
            (
                payload.thesis,
                payload.invalidation,
                date.today().isoformat() if payload.mark_reviewed else None,
                now_iso(),
                ticker,
            ),
        )
        guardada = thesis_mod.load(conn, ticker)
    return {"ok": True, "thesis": guardada.to_dict()}


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
