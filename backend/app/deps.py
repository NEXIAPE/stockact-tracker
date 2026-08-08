"""Dependencias compartidas de la API: perfil, estrategia y cartera cargados."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException

from .core.datapoint import DataPoint, Source
from .core.portfolio import PortfolioState, load_portfolio
from .core.profile import Profile, Strategy, derive_strategy


class ProfileMissing(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail={
                "error": "perfil_no_definido",
                "message": (
                    "Todavía no has completado el onboarding. Sin tu perfil no puedo "
                    "personalizar nada, y personalizar es justamente el punto de esta "
                    "herramienta."
                ),
                "next_step": "POST /api/profile",
            },
        )


def load_profile(conn) -> Optional[Profile]:
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return Profile.from_row(row) if row else None


def require_profile(conn) -> Tuple[Profile, Strategy]:
    profile = load_profile(conn)
    if profile is None:
        raise ProfileMissing()
    return profile, derive_strategy(profile)


def context(conn, today: Optional[date] = None) -> Tuple[Profile, Strategy, PortfolioState]:
    profile, strategy = require_profile(conn)
    state = load_portfolio(conn, today=today)
    return profile, strategy, state


# Etiquetas legibles para los datos que registras tú a mano.
_FACT_LABELS = {
    "expense_ratio": "Ratio de gastos del fondo",
    "dividend_yield": "Rentabilidad por dividendo",
    "aum": "Patrimonio del fondo",
    "holdings_count": "Número de posiciones del fondo",
}


def load_user_facts(conn, ticker: str) -> List[DataPoint]:
    rows = conn.execute(
        "SELECT * FROM user_facts WHERE UPPER(ticker) = ?", (ticker.strip().upper(),)
    ).fetchall()
    out: List[DataPoint] = []
    for r in rows:
        try:
            as_of = date.fromisoformat(r["as_of"])
        except (ValueError, TypeError):
            continue
        try:
            retrieved = datetime.fromisoformat(r["created_at"])
        except (ValueError, TypeError):
            retrieved = datetime.now()
        out.append(
            DataPoint(
                label=_FACT_LABELS.get(r["key"], r["key"]),
                value=float(r["value"]),
                unit=r["unit"],
                as_of=as_of,
                source=Source(
                    name=f"{r['source_label']} (registrado por ti)",
                    url=r["source_url"] or "",
                    retrieved_at=retrieved,
                ),
                precision=2,
            )
        )
    return out
