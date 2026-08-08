"""
Perfil del inversor y estrategia mínima derivada.

El onboarding recoge cinco cosas: cuánto vas a invertir, cuánto aportas al mes,
cuánto riesgo toleras, a cuántos años inviertes y para qué. De ahí sale una
"estrategia mínima": una asignación objetivo entre acciones y bonos, un tamaño
máximo por posición y un tope de exposición a acciones individuales.

Todos los números de la estrategia se DERIVAN de lo que tú declaraste, así que
son datos citables con fuente "Tus datos" y fecha de tu último cambio de
perfil. Ninguno sale de la nada.

Las reglas de asignación son convenciones estándar y conservadoras para un
principiante, no una optimización sofisticada. Se documentan explícitamente
para que puedas discutirlas en vez de tener que confiar a ciegas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional

RISK_LEVELS = ("conservador", "moderado", "agresivo")
EXPERIENCE_LEVELS = ("principiante", "intermedio", "avanzado")


@dataclass
class Profile:
    initial_capital: float
    monthly_contribution: float
    risk_tolerance: str
    horizon_years: int
    goals: List[str]
    experience: str = "principiante"
    base_currency: str = "USD"
    emergency_fund_ok: bool = False
    notes: str = ""
    updated_at: Optional[date] = None

    @classmethod
    def from_row(cls, row) -> "Profile":
        import json

        try:
            goals = json.loads(row["goals"])
        except (ValueError, TypeError):
            goals = []
        try:
            updated = datetime.fromisoformat(row["updated_at"]).date()
        except (ValueError, TypeError):
            updated = date.today()
        return cls(
            initial_capital=float(row["initial_capital"]),
            monthly_contribution=float(row["monthly_contribution"]),
            risk_tolerance=row["risk_tolerance"],
            horizon_years=int(row["horizon_years"]),
            goals=goals if isinstance(goals, list) else [],
            experience=row["experience"],
            base_currency=row["base_currency"],
            emergency_fund_ok=bool(row["emergency_fund_ok"]),
            notes=row["notes"] or "",
            updated_at=updated,
        )


@dataclass
class Strategy:
    """Estrategia mínima derivada del perfil. Todo en porcentaje de la cartera."""

    target_stocks_pct: float
    target_bonds_pct: float
    max_position_pct: float          # tope por posición individual
    max_single_stock_pct: float      # tope para una ACCIÓN individual (más estricto)
    max_sector_pct: float
    min_cash_pct: float
    max_cash_pct: float
    core_satellite_note: str
    rationale: List[str]

    def to_dict(self) -> dict:
        return {
            "target_stocks_pct": self.target_stocks_pct,
            "target_bonds_pct": self.target_bonds_pct,
            "max_position_pct": self.max_position_pct,
            "max_single_stock_pct": self.max_single_stock_pct,
            "max_sector_pct": self.max_sector_pct,
            "min_cash_pct": self.min_cash_pct,
            "max_cash_pct": self.max_cash_pct,
            "core_satellite_note": self.core_satellite_note,
            "rationale": self.rationale,
        }


# Asignación base acciones/bonos por tolerancia al riesgo, ajustada por horizonte.
_BASE_STOCKS = {"conservador": 50.0, "moderado": 70.0, "agresivo": 85.0}

# Tope por posición: cuanto menos riesgo toleras, más pequeña cada apuesta.
_BASE_MAX_POSITION = {"conservador": 15.0, "moderado": 20.0, "agresivo": 25.0}

# Tope para una ACCIÓN individual. Deliberadamente bajo para un principiante:
# una sola empresa puede caer mucho y no recuperarse nunca.
_BASE_MAX_SINGLE_STOCK = {"conservador": 3.0, "moderado": 5.0, "agresivo": 8.0}


def derive_strategy(profile: Profile) -> Strategy:
    risk = profile.risk_tolerance if profile.risk_tolerance in RISK_LEVELS else "moderado"
    stocks = _BASE_STOCKS[risk]
    rationale: List[str] = [
        f"Tu tolerancia al riesgo declarada es «{risk}», que fija el reparto de partida "
        f"entre acciones y bonos.",
    ]

    # Horizonte: más años permiten aguantar más caídas; menos años obligan a bajar riesgo.
    if profile.horizon_years >= 15:
        stocks += 10.0
        rationale.append(
            "Con un horizonte de quince años o más puedes aguantar caídas largas, así que "
            "la parte en acciones sube."
        )
    elif profile.horizon_years >= 10:
        stocks += 5.0
        rationale.append("Un horizonte de diez años o más permite algo más de acciones.")
    elif profile.horizon_years <= 3:
        stocks -= 25.0
        rationale.append(
            "Con un horizonte de tres años o menos, el dinero que puedas necesitar pronto "
            "no debería estar en acciones: una caída podría pillarte justo al necesitarlo."
        )
    elif profile.horizon_years <= 5:
        stocks -= 10.0
        rationale.append("Un horizonte corto (cinco años o menos) baja la parte en acciones.")

    # Sin fondo de emergencia, el riesgo real es más alto de lo que parece:
    # una urgencia te obligaría a vender en mal momento.
    if not profile.emergency_fund_ok:
        stocks -= 10.0
        rationale.append(
            "Como no tienes fondo de emergencia, la estrategia reserva más colchón: sin él, "
            "un imprevisto te obligaría a vender en el peor momento."
        )

    # Un principiante empieza con menos riesgo hasta ver cómo reacciona a una caída real.
    if profile.experience == "principiante":
        stocks -= 5.0
        rationale.append(
            "Al empezar, la estrategia va un punto más prudente: la tolerancia al riesgo "
            "sobre el papel y la de verte perder dinero de verdad no siempre coinciden."
        )

    stocks = max(20.0, min(95.0, stocks))
    bonds = 100.0 - stocks

    max_position = _BASE_MAX_POSITION[risk]
    max_single_stock = _BASE_MAX_SINGLE_STOCK[risk]
    if profile.experience == "principiante":
        max_single_stock = min(max_single_stock, 5.0)
        rationale.append(
            "El tope por acción individual se mantiene bajo mientras seas principiante: "
            "la diversificación es la única protección gratuita que existe."
        )

    return Strategy(
        target_stocks_pct=round(stocks, 1),
        target_bonds_pct=round(bonds, 1),
        max_position_pct=max_position,
        max_single_stock_pct=max_single_stock,
        max_sector_pct=30.0,
        min_cash_pct=2.0,
        max_cash_pct=15.0,
        core_satellite_note=(
            "Núcleo y satélite: la mayor parte en ETFs amplios que replican mercados "
            "enteros (el núcleo), y sólo una porción pequeña en ideas concretas que "
            "quieras probar (los satélites). Así una idea equivocada no te arruina el plan."
        ),
        rationale=rationale,
    )


def profile_dict(profile: Profile, strategy: Strategy) -> dict:
    return {
        "initial_capital": profile.initial_capital,
        "monthly_contribution": profile.monthly_contribution,
        "risk_tolerance": profile.risk_tolerance,
        "horizon_years": profile.horizon_years,
        "goals": profile.goals,
        "experience": profile.experience,
        "base_currency": profile.base_currency,
        "emergency_fund_ok": profile.emergency_fund_ok,
        "notes": profile.notes,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "strategy": strategy.to_dict(),
    }


def risk_appetite_score(profile: Profile) -> float:
    """0 (muy prudente) a 1 (muy tolerante). Se usa para juzgar volatilidad."""
    base = {"conservador": 0.2, "moderado": 0.5, "agresivo": 0.8}.get(
        profile.risk_tolerance, 0.5
    )
    if profile.horizon_years >= 15:
        base += 0.1
    if profile.horizon_years <= 3:
        base -= 0.2
    if not profile.emergency_fund_ok:
        base -= 0.1
    return max(0.0, min(1.0, base))


# Umbral de volatilidad anualizada (%) que se considera "alta" para cada perfil.
VOLATILITY_TOLERANCE: Dict[str, float] = {
    "conservador": 18.0,
    "moderado": 28.0,
    "agresivo": 40.0,
}


def volatility_ceiling(profile: Profile) -> float:
    return VOLATILITY_TOLERANCE.get(profile.risk_tolerance, 28.0)
