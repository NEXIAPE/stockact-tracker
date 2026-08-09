"""Análisis bajo demanda: «¿debería comprar/vender X?»."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..core.guards import HardRuleViolation
from ..core.ideas import ALTERNATIVES_NOTICE
from ..core.ideas import generate as generate_ideas
from ..core.recommendation import InsufficientData, analyze
from ..db import get_conn
from ..core import thesis as thesis_mod
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
                          asset_type_hint=asset_type, user_facts=facts,
                          position_thesis=thesis_mod.load(conn, ticker))
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


@router.get("/prices/{ticker}")
def price_series(ticker: str, days: int = Query(default=365, ge=30, le=1825)):
    """Serie de cierres para dibujar, con su media de 200 días.

    Se devuelve submuestreada: un gráfico de unos cientos de puntos se ve igual
    que uno de miles y pesa mucho menos. Los valores son cierres reales, nunca
    interpolados, y viaja la cita de quién los sirvió.
    """
    from ..core import indicators as ind
    from ..providers import prices as price_provider
    from ..providers.http import FetchError

    try:
        serie = price_provider.fetch_daily(ticker)
    except FetchError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "sin_precios",
                "ticker": ticker.upper(),
                "message": str(exc),
            },
        ) from exc

    bars = serie.bars[-days:]
    # Submuestreo tomando puntos reales, sin promediar: promediar inventaría
    # cierres que nunca existieron.
    paso = max(1, len(bars) // 400)
    muestra = bars[::paso]
    if muestra and muestra[-1] is not bars[-1]:
        muestra.append(bars[-1])   # el último cierre siempre se conserva

    sma200 = ind.sma(serie, 200)
    return {
        "ticker": serie.ticker,
        "points": [{"d": b.day.isoformat(), "c": round(b.close, 4)} for b in muestra],
        "sma200": round(sma200.value, 4) if hasattr(sma200, "value") else None,
        "sma200_missing": None if hasattr(sma200, "value") else sma200.reason,
        "last": {"day": serie.last.day.isoformat(), "close": round(serie.last.close, 4)},
        "source_name": serie.source.name,
        "source_url": serie.source.url,
        "total_bars": len(serie.bars),
    }
