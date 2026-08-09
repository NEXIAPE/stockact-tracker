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
from . import thesis as thesis_mod
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


def _today_summary(
    state: PortfolioState,
    unread: List[dict],
    deviations: List,
    thesis_notes: List[str],
) -> dict:
    """Lo único que necesitas saber al abrir: ¿hay algo que hacer hoy?

    Existe porque hasta ahora había que leer cuatro bloques para averiguarlo, y
    la respuesta correcta la mayoría de los días es «no». Decirlo alto y claro
    es una función del producto, no un hueco: una herramienta que cada mañana
    parece tener algo urgente acaba enseñándote a operar de más.
    """
    if state.is_empty():
        return {
            "status": "empezar",
            "headline": "Empieza por registrar lo que ya tienes.",
            "explanation": (
                "El primer paso no es comprar nada. Anota tus posiciones y tu efectivo "
                "para que todo lo demás se calcule sobre datos reales y no sobre supuestos."
            ),
            "items": [{"text": "Registrar cartera y efectivo", "where": "/cartera"}],
        }

    items: List[dict] = []
    if unread:
        items.append({
            "text": f"{len(unread)} alerta(s) sin leer",
            "where": "/alertas",
        })
    atencion = [d for d in deviations if d.severity == "atencion"]
    if atencion:
        items.append({
            "text": f"{len(atencion)} desvío(s) frente a tu estrategia",
            "where": "/cartera",
        })
    if thesis_notes:
        items.append({
            "text": "Falta anotar por qué compraste alguna posición",
            "where": "/cartera",
        })
    if state.missing_prices:
        items.append({
            "text": "No se pudo valorar alguna posición",
            "where": "/cartera",
        })

    if not items:
        return {
            "status": "nada_que_hacer",
            "headline": "Hoy no hay nada que hacer.",
            "explanation": (
                "Tu cartera sigue alineada con tu plan y no hay nada pendiente de mirar. "
                "Un día sin decisiones es el estado normal de una cartera de largo plazo, "
                "no una señal de que falte algo."
            ),
            "items": [],
        }

    return {
        "status": "algo_que_mirar",
        "headline": (
            "Hay algo que vale la pena mirar cuando tengas un rato."
            if len(items) == 1
            else "Hay unas cuantas cosas que vale la pena mirar cuando tengas un rato."
        ),
        # Nota: el guardián anti-FOMO caza la palabra «urgente» aunque vaya
        # negada. Se reescribe la frase en vez de ablandar el guardián: un
        # linter tosco que obliga a reformular de vez en cuando es mejor que uno
        # listo al que se le pueda colar lo que debía bloquear.
        "explanation": (
            "Nada de esto pide que actúes hoy. Están ordenadas por lo que más suele "
            "importar."
        ),
        "items": items[:4],
    }


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

    # Los desvios de cartera generan alertas, asi que sin esto la misma
    # informacion aparecia DOS VECES seguidas en la pantalla, con las mismas
    # cifras: primero como alerta y justo debajo como desvio. Se marca cual ya
    # esta arriba para que el frontend no lo repita.
    cuerpos_alertados = " ".join(a["body"] for a in unread)
    for d in deviations:
        d.already_alerted = d.message[:60] in cuerpos_alertados

    ideas: List[dict] = []
    idea_problems: List[str] = []
    if include_ideas:
        generated, idea_problems = generate_ideas(conn, profile, strategy, state, limit=3, today=today)
        ideas = [i.to_dict() for i in generated]

    # Tesis ausentes o sin revisar. Va antes que el estado de los datos porque
    # es un hueco tuyo, no de las fuentes, y es el que más pesa al decidir ventas.
    theses = thesis_mod.load_all(conn)
    thesis_notes: List[str] = [
        n for n in (
            thesis_mod.missing_thesis_warning(theses),
            thesis_mod.stale_thesis_warning(theses, today),
        ) if n
    ]

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
        "today": _today_summary(state, unread, deviations, thesis_notes),
        "headline": _headline(state, len(unread), len(deviations)),
        "portfolio": portfolio_dict(state, profile, strategy),
        "unread_alerts": unread,
        "deviations": [
            {**d.to_dict(today), "already_alerted": getattr(d, "already_alerted", False)}
            for d in deviations
        ],
        "ideas": ideas,
        "ideas_sizing_notice": ALTERNATIVES_NOTICE,
        "thesis_notes": thesis_notes,
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
