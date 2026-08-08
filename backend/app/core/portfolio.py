"""
Estado de la cartera: valoración, concentración, diversificación y desvíos.

Los precios vienen del proveedor real; si falta el precio de una posición, esa
posición se valora como "no disponible" y el total lo declara explícitamente,
en vez de sumar un cero que te haría creer que tienes menos de lo que tienes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from ..providers import stooq
from ..providers.http import FetchError
from .datapoint import DataPoint, Missing, Source, user_source
from .profile import Profile, Strategy
from .universe import guess_asset_type, is_broad_etf, lookup_etf

# Sectores: se reutiliza el mapa offline que ya existía en el repo para el
# rastreador STOCK Act. Es un mapa parcial y lo dice: lo que no conoce es
# "Desconocido", no se adivina.
try:  # pragma: no cover - depende del layout del repo
    import sys
    from pathlib import Path

    _root = str(Path(__file__).resolve().parents[3])
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from sectors import lookup_sector  # type: ignore
except Exception:  # pragma: no cover
    def lookup_sector(ticker: str) -> str:  # type: ignore
        return "Unknown"


SECTOR_ES = {
    "Information Technology": "Tecnología",
    "Communication Services": "Comunicaciones",
    "Consumer Discretionary": "Consumo discrecional",
    "Consumer Staples": "Consumo básico",
    "Financials": "Financiero",
    "Health Care": "Salud",
    "Energy": "Energía",
    "Industrials": "Industrial",
    "Utilities": "Servicios públicos",
    "Real Estate": "Inmobiliario",
    "Materials": "Materiales",
    "Unknown": "Desconocido",
}


def sector_of(ticker: str, asset_type: str) -> str:
    if asset_type == "etf":
        info = lookup_etf(ticker)
        if info and info.asset_class == "bonos":
            return "Bonos"
        return "Diversificado (ETF)"
    return SECTOR_ES.get(lookup_sector(ticker), "Desconocido")


# Tope efectivo para "sin tope": un ETF amplio ya está diversificado por dentro,
# así que concentrarse en él no es concentrarse en nada.
NO_CAP = 100.0


def position_cap(ticker: str, asset_type: str, strategy: Strategy) -> float:
    """Peso máximo razonable para una posición, según lo que sea.

    La distinción importa: tener el 70 % en un ETF de mercado total NO es estar
    concentrado (por dentro son miles de empresas), mientras que tener el 70 %
    en una sola acción sí lo es. Aplicar el mismo tope a los dos casos daría
    avisos absurdos y acabaría enseñándote a ignorarlos.
    """
    if asset_type == "etf":
        return NO_CAP if is_broad_etf(ticker) else strategy.max_position_pct
    return strategy.max_single_stock_pct


def cap_explanation(ticker: str, asset_type: str) -> str:
    if asset_type == "etf" and is_broad_etf(ticker):
        return (
            "Es un ETF amplio: por dentro ya reparte entre muchísimas empresas, así que no "
            "se le aplica tope por posición."
        )
    if asset_type == "etf":
        return "Es un ETF sectorial o temático: concentra en un tipo de empresa, así que sí lleva tope."
    return "Es una acción individual, y ahí el tope es más estricto."


@dataclass
class Position:
    ticker: str
    shares: float
    avg_cost: float
    asset_type: str
    notes: str = ""
    price: Optional[DataPoint] = None
    price_error: str = ""

    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_cost

    @property
    def market_value(self) -> Optional[float]:
        return self.shares * self.price.value if self.price else None

    @property
    def sector(self) -> str:
        return sector_of(self.ticker, self.asset_type)

    def to_dict(self, total_value: Optional[float], today: date) -> dict:
        mv = self.market_value
        weight = (mv / total_value * 100.0) if (mv is not None and total_value) else None
        gain = (mv - self.cost_basis) if mv is not None else None
        gain_pct = (
            (mv / self.cost_basis - 1.0) * 100.0
            if mv is not None and self.cost_basis > 0
            else None
        )
        return {
            "ticker": self.ticker,
            "shares": self.shares,
            "avg_cost": self.avg_cost,
            "asset_type": self.asset_type,
            "is_broad_etf": is_broad_etf(self.ticker),
            "sector": self.sector,
            "notes": self.notes,
            "cost_basis": round(self.cost_basis, 2),
            "price": self.price.to_dict(today) if self.price else None,
            "price_error": self.price_error,
            "market_value": round(mv, 2) if mv is not None else None,
            "weight_pct": round(weight, 2) if weight is not None else None,
            "unrealized_gain": round(gain, 2) if gain is not None else None,
            "unrealized_gain_pct": round(gain_pct, 2) if gain_pct is not None else None,
        }


@dataclass
class PortfolioState:
    positions: List[Position]
    cash: float
    cash_updated: Optional[date]
    invested_value: Optional[float]
    total_value: Optional[float]
    missing_prices: List[str] = field(default_factory=list)
    as_of: date = field(default_factory=date.today)

    # -- métricas ----------------------------------------------------------
    def weights(self) -> Dict[str, float]:
        if not self.total_value:
            return {}
        out = {}
        for p in self.positions:
            mv = p.market_value
            if mv is not None:
                out[p.ticker] = mv / self.total_value * 100.0
        return out

    def sector_weights(self) -> Dict[str, float]:
        if not self.total_value:
            return {}
        acc: Dict[str, float] = {}
        for p in self.positions:
            mv = p.market_value
            if mv is None:
                continue
            acc[p.sector] = acc.get(p.sector, 0.0) + mv / self.total_value * 100.0
        return acc

    def cash_pct(self) -> Optional[float]:
        if not self.total_value:
            return None
        return self.cash / self.total_value * 100.0

    def stocks_vs_bonds(self) -> Dict[str, Optional[float]]:
        if not self.total_value:
            return {"acciones": None, "bonos": None}
        stock_v = 0.0
        bond_v = 0.0
        for p in self.positions:
            mv = p.market_value
            if mv is None:
                continue
            info = lookup_etf(p.ticker)
            if info and info.asset_class == "bonos":
                bond_v += mv
            else:
                stock_v += mv
        return {
            "acciones": stock_v / self.total_value * 100.0,
            "bonos": bond_v / self.total_value * 100.0,
        }

    def largest_position(self) -> Optional[tuple[str, float]]:
        w = self.weights()
        if not w:
            return None
        ticker = max(w, key=lambda k: w[k])
        return ticker, w[ticker]

    def individual_stock_pct(self) -> float:
        """Porcentaje de la cartera en acciones individuales (no ETFs)."""
        if not self.total_value:
            return 0.0
        v = sum(
            p.market_value or 0.0 for p in self.positions if p.asset_type != "etf"
        )
        return v / self.total_value * 100.0

    def is_empty(self) -> bool:
        return not self.positions and self.cash <= 0


def load_portfolio(conn, today: Optional[date] = None) -> PortfolioState:
    """Lee la cartera de la base y la valora con precios reales."""
    today = today or date.today()

    rows = conn.execute("SELECT * FROM holdings ORDER BY ticker").fetchall()
    cash_row = conn.execute("SELECT * FROM cash WHERE id = 1").fetchone()
    cash = float(cash_row["amount"]) if cash_row else 0.0
    cash_updated = None
    if cash_row:
        try:
            cash_updated = date.fromisoformat(cash_row["updated_at"][:10])
        except (ValueError, TypeError):
            cash_updated = None

    positions: List[Position] = []
    missing: List[str] = []
    invested = 0.0
    any_price = False

    for row in rows:
        ticker = row["ticker"].upper()
        asset_type = guess_asset_type(ticker, row["asset_type"])
        pos = Position(
            ticker=ticker,
            shares=float(row["shares"]),
            avg_cost=float(row["avg_cost"]),
            asset_type=asset_type,
            notes=row["notes"] or "",
        )
        try:
            series = stooq.fetch_daily(ticker)
            bar = series.last
            pos.price = DataPoint(
                label="Último cierre",
                value=bar.close,
                unit="USD",
                as_of=bar.day,
                source=series.source,
            )
            invested += pos.shares * bar.close
            any_price = True
        except FetchError as exc:
            pos.price_error = str(exc)
            missing.append(ticker)
        positions.append(pos)

    invested_value = invested if any_price or not positions else None
    total = None
    if invested_value is not None:
        total = invested_value + cash
    elif not positions:
        total = cash

    return PortfolioState(
        positions=positions,
        cash=cash,
        cash_updated=cash_updated,
        invested_value=invested_value,
        total_value=total,
        missing_prices=missing,
        as_of=today,
    )


# ---------------------------------------------------------------------------
# Chequeos de concentración y desvío frente a la estrategia
# ---------------------------------------------------------------------------
@dataclass
class Deviation:
    kind: str          # "concentracion" | "sector" | "cash" | "asignacion" | "acciones_individuales"
    severity: str      # "informativo" | "atencion"
    message: str
    numbers: List[DataPoint] = field(default_factory=list)

    def to_dict(self, today: date) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "numbers": [n.to_dict(today) for n in self.numbers],
        }


def _dp(label: str, value: float, unit: str, today: date, src: Source, precision: int = 1) -> DataPoint:
    return DataPoint(label=label, value=value, unit=unit, as_of=today, source=src, precision=precision)


def check_deviations(
    state: PortfolioState, profile: Profile, strategy: Strategy
) -> List[Deviation]:
    """Desvíos entre tu cartera real y tu estrategia. Tono informativo, sin prisa."""
    out: List[Deviation] = []
    today = state.as_of
    src = user_source()

    if state.total_value is None or state.total_value <= 0:
        return out

    # 1. Concentración por posición. Se evalúan todas, no sólo la mayor: puedes
    # estar pasado de tope en dos acciones a la vez.
    for ticker, weight in sorted(state.weights().items(), key=lambda kv: -kv[1]):
        pos = next((p for p in state.positions if p.ticker == ticker), None)
        limit = position_cap(ticker, pos.asset_type if pos else "accion", strategy)
        if limit < NO_CAP and weight > limit:
            kind_txt = "una sola acción" if pos and pos.asset_type != "etf" else "una sola posición"
            out.append(
                Deviation(
                    kind="concentracion",
                    severity="atencion",
                    message=(
                        f"Tienes más peso en {kind_txt} ({ticker}) del que tu propia estrategia "
                        f"marca como tope. No es una emergencia y no hay que hacer nada hoy, "
                        f"pero conviene tenerlo presente en tu próximo aporte: podrías comprar "
                        f"otra cosa en vez de más {ticker}."
                    ),
                    numbers=[
                        _dp(f"Peso de {ticker} en tu cartera", weight, "%", today, src),
                        _dp("Tope que fijaste en tu estrategia", limit, "%", today, src),
                    ],
                )
            )

    # 2. Exposición total a acciones individuales (protección de principiante).
    indiv = state.individual_stock_pct()
    indiv_ceiling = 20.0 if profile.experience == "principiante" else 40.0
    if indiv > indiv_ceiling:
        out.append(
            Deviation(
                kind="acciones_individuales",
                severity="atencion",
                message=(
                    "Una parte grande de tu cartera está en acciones de empresas concretas "
                    "en lugar de en ETFs que reparten el riesgo entre cientos de empresas. "
                    "Acertar con empresas individuales es difícil incluso para profesionales; "
                    "por eso la recomendación general para quien empieza es que el núcleo sea "
                    "de fondos amplios."
                ),
                numbers=[
                    _dp("En acciones individuales", indiv, "%", today, src),
                    _dp("Referencia para tu nivel de experiencia", indiv_ceiling, "%", today, src),
                ],
            )
        )

    # 3. Sectores.
    for sector, weight in state.sector_weights().items():
        if sector in ("Diversificado (ETF)", "Bonos", "Desconocido"):
            continue
        if weight > strategy.max_sector_pct:
            out.append(
                Deviation(
                    kind="sector",
                    severity="atencion",
                    message=(
                        f"El sector {sector} pesa más en tu cartera que el tope de tu estrategia. "
                        f"Cuando un sector entero cae, todo lo que tengas ahí cae junto."
                    ),
                    numbers=[
                        _dp(f"Peso del sector {sector}", weight, "%", today, src),
                        _dp("Tope por sector en tu estrategia", strategy.max_sector_pct, "%", today, src),
                    ],
                )
            )

    # 4. Efectivo.
    cash_pct = state.cash_pct()
    if cash_pct is not None:
        if cash_pct > strategy.max_cash_pct:
            out.append(
                Deviation(
                    kind="cash",
                    severity="informativo",
                    message=(
                        "Tienes más efectivo parado del que tu estrategia contempla. No es un "
                        "problema urgente: el efectivo no pierde valor de golpe. Simplemente no "
                        "está trabajando para tus objetivos."
                    ),
                    numbers=[
                        _dp("Efectivo sobre el total", cash_pct, "%", today, src),
                        _dp("Máximo de efectivo en tu estrategia", strategy.max_cash_pct, "%", today, src),
                    ],
                )
            )
        elif cash_pct < strategy.min_cash_pct and state.positions:
            out.append(
                Deviation(
                    kind="cash",
                    severity="informativo",
                    message=(
                        "Estás casi sin efectivo en la cuenta de inversión. Tener un poco de "
                        "colchón evita quedarte sin margen si aparece algo que sí quieras comprar."
                    ),
                    numbers=[
                        _dp("Efectivo sobre el total", cash_pct, "%", today, src),
                        _dp("Mínimo de efectivo en tu estrategia", strategy.min_cash_pct, "%", today, src),
                    ],
                )
            )

    # 5. Asignación acciones / bonos frente al objetivo.
    mix = state.stocks_vs_bonds()
    if mix["acciones"] is not None and state.positions:
        drift = mix["acciones"] - strategy.target_stocks_pct
        if abs(drift) >= 10.0:
            direction = "por encima" if drift > 0 else "por debajo"
            out.append(
                Deviation(
                    kind="asignacion",
                    severity="informativo",
                    message=(
                        f"Tu peso en acciones está {direction} del objetivo que salió de tu perfil. "
                        f"Se corrige sin vender nada: basta con dirigir los próximos aportes "
                        f"mensuales al lado que va corto."
                    ),
                    numbers=[
                        _dp("Peso actual en acciones", mix["acciones"], "%", today, src),
                        _dp("Objetivo de tu estrategia", strategy.target_stocks_pct, "%", today, src),
                    ],
                )
            )

    return out


def portfolio_dict(
    state: PortfolioState,
    profile: Optional[Profile],
    strategy: Optional[Strategy],
) -> dict:
    today = state.as_of
    deviations = (
        check_deviations(state, profile, strategy) if profile and strategy else []
    )
    return {
        "as_of": today.isoformat(),
        "cash": round(state.cash, 2),
        "cash_updated": state.cash_updated.isoformat() if state.cash_updated else None,
        "invested_value": round(state.invested_value, 2) if state.invested_value is not None else None,
        "total_value": round(state.total_value, 2) if state.total_value is not None else None,
        "cash_pct": round(state.cash_pct(), 2) if state.cash_pct() is not None else None,
        "positions": [p.to_dict(state.total_value, today) for p in state.positions],
        "sector_weights": {k: round(v, 2) for k, v in state.sector_weights().items()},
        "stocks_vs_bonds": {
            k: (round(v, 2) if v is not None else None)
            for k, v in state.stocks_vs_bonds().items()
        },
        "individual_stock_pct": round(state.individual_stock_pct(), 2),
        "missing_prices": state.missing_prices,
        "data_warning": (
            "No se pudo obtener el precio de: " + ", ".join(state.missing_prices) +
            ". El valor total mostrado NO incluye esas posiciones."
        ) if state.missing_prices else "",
        "deviations": [d.to_dict(today) for d in deviations],
    }
