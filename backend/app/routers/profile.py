"""Onboarding y perfil. Un solo usuario: fila única."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.profile import derive_strategy, profile_dict
from ..db import dumps, get_conn, now_iso
from ..deps import load_profile
from ..schemas import ProfileIn

router = APIRouter(prefix="/api/profile", tags=["perfil"])


ONBOARDING_STEPS = [
    {
        "id": "capital",
        "title": "¿Con cuánto empiezas?",
        "help": (
            "El dinero que vas a poner a invertir ahora. Que sea dinero que no vas a "
            "necesitar en los próximos años: lo invertido puede bajar y tardar en recuperarse."
        ),
        "field": "initial_capital",
        "type": "money",
    },
    {
        "id": "aporte",
        "title": "¿Cuánto puedes aportar cada mes?",
        "help": (
            "Aportar poco y siempre suele funcionar mejor que acertar el momento. Si no lo "
            "sabes aún, pon cero y lo cambias después."
        ),
        "field": "monthly_contribution",
        "type": "money",
    },
    {
        "id": "riesgo",
        "title": "¿Cuánto riesgo aguantas?",
        "help": (
            "No es cuánto quieres ganar, es cuánto puedes ver caer sin vender. Piensa en "
            "concreto: si tu cartera bajara un tercio en unos meses, ¿aguantarías sin tocarla?"
        ),
        "field": "risk_tolerance",
        "type": "choice",
        "options": [
            {"value": "conservador", "label": "Conservador",
             "help": "Prefiero ganar menos a cambio de sobresaltos pequeños."},
            {"value": "moderado", "label": "Moderado",
             "help": "Acepto caídas fuertes de vez en cuando si a largo plazo compensa."},
            {"value": "agresivo", "label": "Agresivo",
             "help": "Puedo ver caer mucho mi cartera sin cambiar de plan."},
        ],
    },
    {
        "id": "horizonte",
        "title": "¿A cuántos años inviertes?",
        "help": (
            "Cuándo esperas necesitar este dinero. Cuanto más lejos, más caídas puedes "
            "aguantar por el camino."
        ),
        "field": "horizon_years",
        "type": "number",
    },
    {
        "id": "objetivos",
        "title": "¿Para qué es este dinero?",
        "help": (
            "Escribe tus objetivos con tus palabras. Sirven para recordarte por qué "
            "empezaste cuando el mercado se ponga feo."
        ),
        "field": "goals",
        "type": "list",
    },
    {
        "id": "emergencia",
        "title": "¿Tienes un fondo de emergencia?",
        "help": (
            "Unos meses de gastos guardados aparte, líquidos. Es lo que evita que un "
            "imprevisto te obligue a vender inversiones en el peor momento. Si no lo tienes, "
            "la estrategia lo tendrá en cuenta y será más prudente."
        ),
        "field": "emergency_fund_ok",
        "type": "bool",
    },
    {
        "id": "experiencia",
        "title": "¿Cuánta experiencia tienes invirtiendo?",
        "help": (
            "Si eres principiante, la herramienta será más estricta con la diversificación "
            "y te avisará antes si te concentras demasiado."
        ),
        "field": "experience",
        "type": "choice",
        "options": [
            {"value": "principiante", "label": "Principiante", "help": "Estoy empezando."},
            {"value": "intermedio", "label": "Intermedio", "help": "Llevo un tiempo."},
            {"value": "avanzado", "label": "Avanzado", "help": "Sé lo que hago."},
        ],
    },
]


@router.get("/onboarding")
def onboarding():
    """Los pasos del onboarding, con la explicación de por qué se pregunta cada cosa."""
    return {"steps": ONBOARDING_STEPS}


@router.get("")
def get_profile():
    with get_conn() as conn:
        profile = load_profile(conn)
        if profile is None:
            return {"configured": False, "profile": None}
        return {"configured": True, "profile": profile_dict(profile, derive_strategy(profile))}


@router.post("")
def save_profile(payload: ProfileIn):
    """Guarda (o reemplaza) tu perfil y devuelve la estrategia que se deriva de él."""
    with get_conn() as conn:
        existing = conn.execute("SELECT created_at FROM profile WHERE id = 1").fetchone()
        created = existing["created_at"] if existing else now_iso()
        conn.execute(
            """
            INSERT INTO profile (
                id, initial_capital, monthly_contribution, risk_tolerance, horizon_years,
                goals, experience, base_currency, emergency_fund_ok, notes, created_at, updated_at
            ) VALUES (1,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                initial_capital = excluded.initial_capital,
                monthly_contribution = excluded.monthly_contribution,
                risk_tolerance = excluded.risk_tolerance,
                horizon_years = excluded.horizon_years,
                goals = excluded.goals,
                experience = excluded.experience,
                base_currency = excluded.base_currency,
                emergency_fund_ok = excluded.emergency_fund_ok,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                payload.initial_capital,
                payload.monthly_contribution,
                payload.risk_tolerance,
                payload.horizon_years,
                dumps(payload.goals),
                payload.experience,
                payload.base_currency,
                1 if payload.emergency_fund_ok else 0,
                payload.notes,
                created,
                now_iso(),
            ),
        )
        profile = load_profile(conn)
        strategy = derive_strategy(profile)
        return {
            "configured": True,
            "profile": profile_dict(profile, strategy),
            "explanation": (
                "Esta estrategia no sale de ninguna fórmula secreta: sale de lo que acabas de "
                "responder. Cada regla lleva su porqué para que puedas discutirla en vez de "
                "tener que confiar a ciegas."
            ),
        }
