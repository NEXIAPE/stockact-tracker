"""Briefing diario y alertas."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..core import alerts as alerts_core
from ..core.briefing import build
from ..db import get_conn, now_iso
from ..deps import context

router = APIRouter(prefix="/api", tags=["briefing"])


@router.get("/briefing")
def daily_briefing(
    include_ideas: bool = Query(default=True),
    with_prices: bool = Query(default=True),
):
    """Resumen priorizado del día: cartera, alertas, desvíos e ideas.

    Se pide en tres tandas para que la pantalla no se quede en blanco:
    ``with_prices=false`` devuelve al instante lo que ya está guardado (alertas
    sin leer, tesis pendientes), luego la versión valorada, y las ideas al
    final porque analizan varios símbolos y son lo que más tarda.
    """
    with get_conn() as conn:
        profile, strategy, state = context(conn, with_prices=with_prices)
        return build(conn, profile, strategy, state, include_ideas=include_ideas)


@router.get("/alerts")
def get_alerts(only_unread: bool = Query(default=False), limit: int = Query(default=50, le=200)):
    with get_conn() as conn:
        items = alerts_core.list_alerts(conn, only_unread=only_unread, limit=limit)
    return {
        "alerts": items,
        "framing": (
            "Las alertas señalan cosas que vale la pena mirar. Ninguna es una orden ni "
            "requiere que actúes hoy."
        ),
    }


@router.post("/alerts/refresh")
def refresh_alerts():
    """Revisa tus posiciones y tu watchlist y genera las alertas nuevas."""
    with get_conn() as conn:
        profile, strategy, state = context(conn)
        result = alerts_core.generate_and_store(conn, profile, strategy, state)
    return result


@router.post("/alerts/{alert_id}/read")
def mark_read(alert_id: int):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE alerts SET read_at = ? WHERE id = ? AND read_at IS NULL",
            (now_iso(), alert_id),
        )
        if cur.rowcount == 0:
            exists = conn.execute("SELECT 1 FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if not exists:
                raise HTTPException(404, "Esa alerta no existe.")
    return {"ok": True}


@router.post("/alerts/read-all")
def mark_all_read():
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE alerts SET read_at = ? WHERE read_at IS NULL", (now_iso(),)
        )
    return {"ok": True, "marked": cur.rowcount}
