"""Análisis bajo demanda: «¿debería comprar/vender X?»."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..core.guards import HardRuleViolation
from ..core.ideas import ALTERNATIVES_NOTICE
from ..core.ideas import generate as generate_ideas
from ..core.recommendation import InsufficientData, analyze
from ..db import get_conn
from ..deps import context, load_user_facts

router = APIRouter(prefix="/api", tags=["análisis"])


@router.get("/analyze/{ticker}")
def analyze_ticker(ticker: str, asset_type: str | None = Query(default=None)):
    """Recomendación estructurada completa para un ticker.

    Devuelve idea, tesis, evidencia citada, riesgos, contra-argumento, encaje
    con tu cartera y nivel de confianza. Si falta alguno de esos bloques, la
    respuesta se bloquea con error: una recomendación incompleta es un defecto.
    """
    with get_conn() as conn:
        profile, strategy, state = context(conn)
        facts = load_user_facts(conn, ticker)

        try:
            rec = analyze(ticker, profile, strategy, state,
                          asset_type_hint=asset_type, user_facts=facts)
        except InsufficientData as exc:
            # No opinamos sin datos. Se dice qué falta y qué se intentó.
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "sin_datos_suficientes",
                    "ticker": exc.ticker,
                    "message": exc.detail,
                    "sources_tried": exc.tried,
                    "what_you_can_do": (
                        "Comprueba que el símbolo sea el que cotiza en EE. UU. Si es correcto, "
                        "puede que la fuente esté caída: vuelve a intentarlo más tarde."
                    ),
                },
            ) from exc
        except HardRuleViolation as exc:
            # Regla dura incumplida: preferimos un error a mostrar algo defectuoso.
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "regla_dura_incumplida",
                    "rule": exc.rule,
                    "message": exc.detail,
                    "explanation": (
                        "La herramienta ha bloqueado su propia respuesta porque incumplía una "
                        "de sus reglas innegociables. Es un fallo del programa, no tuyo."
                    ),
                },
            ) from exc

        return rec.to_dict()


@router.get("/ideas")
def proactive_ideas(limit: int = Query(default=4, ge=1, le=8)):
    """Candidatos que encajan con tu perfil, cada uno con riesgos y contra-caso.

    Son puntos de partida para investigar, no órdenes.
    """
    with get_conn() as conn:
        profile, strategy, state = context(conn)
        ideas, problems = generate_ideas(conn, profile, strategy, state, limit=limit)
    return {
        "ideas": [i.to_dict() for i in ideas],
        "problems": problems,
        "framing": (
            "Estas ideas son un punto de partida para que investigues, no una lista de "
            "compras. Ninguna requiere que hagas nada hoy."
        ),
        "sizing_notice": ALTERNATIVES_NOTICE,
    }
