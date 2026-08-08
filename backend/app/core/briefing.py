"""
Briefing diario: lo primero que ves al abrir la herramienta.

Orden de prioridad, pensado para que lo importante esté arriba y nada empuje a
operar:

  1. Cómo va tu cartera (y qué NO se pudo valorar).
  2. Alertas sin leer.
  3. Desvíos frente a tu propia estrategia.
  4. Ideas que encajan con tu perfil, cada una con sus riesgos y contra-caso.
  5. Qué le falta al briefing de hoy (fuentes caídas, datos viejos).

El briefing termina siempre con el estado de los datos. Si algo no se pudo
obtener, aparece: preferimos que sepas qué NO sabes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from ..db import now_iso
from .alerts import list_alerts
from .guards import NOT_ADVICE_NOTICE, READ_ONLY_NOTICE
from .ideas import ALTERNATIVES_NOTICE
from .ideas import generate as generate_ideas
from .portfolio import PortfolioState, check_deviations, portfolio_dict
from .profile import Profile, Strategy


def _headline(state: PortfolioState, unread: int, deviations: int) -> str:
    """Una frase de resumen. Sin cifras: las cifras van en los bloques citados."""
    if state.is_empty():
        return (
            "Todavía no has registrado cartera. El primer paso no es comprar nada: es "
            "anotar lo que ya tienes y cuánto efectivo hay, para que todo lo demás sea real."
        )
    parts = []
    if unread:
        parts.append("hay alertas que no has leído")
    if deviations:
        parts.append("tu cartera se ha alejado algo de tu estrategia")
    if state.missing_prices:
        parts.append("no se pudo valorar alguna posición por falta de precio")
    if not parts:
        return (
            "Sin novedades que requieran tu atención. Un día sin nada que hacer es un buen "
            "día para una cartera de largo plazo."
        )
    return "Para revisar cuando tengas un rato: " + "; ".join(parts) + "."


def build(
    conn,
    profile: Profile,
    strategy: Strategy,
    state: PortfolioState,
    include_ideas: bool = True,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()

    unread = list_alerts(conn, only_unread=True, limit=20)
    deviations = check_deviations(state, profile, strategy)

    ideas: List[dict] = []
    idea_problems: List[str] = []
    if include_ideas:
        generated, idea_problems = generate_ideas(conn, profile, strategy, state, limit=3, today=today)
        ideas = [i.to_dict() for i in generated]

    data_health: List[str] = []
    if state.missing_prices:
        data_health.append(
            "Sin precio para: " + ", ".join(state.missing_prices) +
            ". El valor total de la cartera no las incluye."
        )
    data_health.extend(idea_problems)

    from ..providers import finnhub, stockact

    if not finnhub.enabled():
        data_health.append(
            "Finnhub no está configurado (falta FINNHUB_API_KEY), así que no hay PER, beta "
            "ni cotización intradía. El análisis usa cierres diarios y fundamentales de la SEC."
        )
    if not stockact.available():
        data_health.append(
            "El rastreador STOCK Act de este repo no tiene base de datos todavía, así que no "
            "hay contexto de divulgaciones del Congreso. Se genera con «python main.py»."
        )

    last_run = conn.execute(
        "SELECT ran_at FROM runs WHERE kind = 'briefing' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.execute("INSERT INTO runs (kind, ran_at) VALUES (?,?)", ("briefing", now_iso()))

    return {
        "date": today.isoformat(),
        "headline": _headline(state, len(unread), len(deviations)),
        "portfolio": portfolio_dict(state, profile, strategy),
        "unread_alerts": unread,
        "deviations": [d.to_dict(today) for d in deviations],
        "ideas": ideas,
        "ideas_sizing_notice": ALTERNATIVES_NOTICE,
        "data_health": data_health,
        "previous_run": last_run["ran_at"] if last_run else None,
        "notices": {
            "read_only": READ_ONLY_NOTICE,
            "not_advice": NOT_ADVICE_NOTICE,
            "no_rush": (
                "Nada de lo que hay aquí requiere que actúes hoy. Operar de más es una de "
                "las formas más fiables de perder dinero invirtiendo."
            ),
        },
    }
