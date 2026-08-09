"""
Motor de recomendación.

Es un motor de REGLAS, deterministas y auditables. No hay un modelo generativo
escribiendo cifras: cada número que sale de aquí procede de un ``DataPoint``
con fuente y fecha, y la prosa se escribe sin cifras a propósito para que sea
imposible colar una inventada.

En qué se basa cada recomendación (los seis frentes que pediste):
  1. Precio y mercado ....... tendencia, volatilidad, caída desde máximos.
  2. Fundamentales .......... SEC EDGAR (acciones); en ETFs se dice que no aplica.
  3. Noticias ............... titulares citados y ETIQUETADOS como interpretación.
  4. Sentimiento ............ sólo si hay dato real; si no, se declara ausente.
  5. Tu cartera ............. concentración, diversificación, efectivo, encaje.
  6. Tu perfil .............. riesgo, horizonte, objetivos, experiencia.

La salida pasa por los guardianes de ``core.guards`` antes de devolverse. Si
falta el contra-argumento o algún riesgo, la respuesta se BLOQUEA con error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from ..config import STALE_PRICE_DAYS
from ..providers import edgar, finnhub, news_rss, prices, stockact
from ..providers.http import FetchError
from . import indicators as ind
from .datapoint import DataPoint, Datum, Missing, Source, derived_source, user_source
from .guards import (
    NOT_ADVICE_NOTICE,
    READ_ONLY_NOTICE,
    assert_no_pressure_language,
    assert_numbers_are_cited,
    assert_recommendation_complete,
    collect_allowed_numbers,
)
from .portfolio import NO_CAP, PortfolioState, cap_explanation, position_cap, sector_of
from .profile import Profile, Strategy, volatility_ceiling
from .universe import guess_asset_type, is_broad_etf, lookup_etf

ACTIONS = ("comprar", "mantener", "evitar", "vender")


class InsufficientData(Exception):
    """No hay datos suficientes para opinar. Se dice claramente en vez de opinar igual."""

    def __init__(self, ticker: str, detail: str, tried: List[str]):
        self.ticker = ticker
        self.detail = detail
        self.tried = tried
        super().__init__(detail)


@dataclass
class Evidence:
    claim: str                       # afirmación en palabras, SIN cifras
    data: List[Datum] = field(default_factory=list)
    kind: str = "precio"             # precio | fundamental | noticia | cartera | perfil | contexto

    def to_dict(self, today: date) -> dict:
        return {
            "claim": self.claim,
            "kind": self.kind,
            "data": [d.to_dict(today) for d in self.data],
        }


@dataclass
class Recommendation:
    ticker: str
    name: str
    asset_type: str
    action: str
    action_label: str
    thesis: str
    suggested_position: dict
    evidence: List[Evidence]
    risks: List[str]
    counter_argument: str
    portfolio_fit: str
    portfolio_fit_data: List[Datum]
    confidence_level: str
    confidence_basis: List[str]
    data_gaps: List[str]
    news: List[dict]
    sentiment: Optional[dict]
    context_signals: List[dict]
    beginner_warnings: List[str]
    score: float
    score_breakdown: List[dict]
    as_of: date

    def all_data(self) -> List[Datum]:
        out: List[Datum] = list(self.portfolio_fit_data)
        for e in self.evidence:
            out.extend(e.data)
        return out

    def to_dict(self) -> dict:
        today = self.as_of
        return {
            "ticker": self.ticker,
            "name": self.name,
            "asset_type": self.asset_type,
            "action": self.action,
            "action_label": self.action_label,
            "thesis": self.thesis,
            "suggested_position": self.suggested_position,
            "evidence": [e.to_dict(today) for e in self.evidence],
            "risks": self.risks,
            "counter_argument": self.counter_argument,
            "portfolio_fit": self.portfolio_fit,
            "portfolio_fit_data": [d.to_dict(today) for d in self.portfolio_fit_data],
            "confidence": {
                "level": self.confidence_level,
                "basis": self.confidence_basis,
                "data_gaps": self.data_gaps,
            },
            "news": self.news,
            "sentiment": self.sentiment,
            "context_signals": self.context_signals,
            "beginner_warnings": self.beginner_warnings,
            "score": round(self.score, 1),
            "score_breakdown": self.score_breakdown,
            "as_of": today.isoformat(),
            "notices": {
                "read_only": READ_ONLY_NOTICE,
                "not_advice": NOT_ADVICE_NOTICE,
                "news_are_interpretation": (
                    "Los titulares son interpretación de terceros, no hechos sobre el "
                    "valor del activo. Van con su fuente y su fecha para que los juzgues tú."
                ),
            },
        }


# ---------------------------------------------------------------------------
# Recolección de datos
# ---------------------------------------------------------------------------
@dataclass
class TickerData:
    ticker: str
    asset_type: str
    name: str
    series: prices.PriceSeries
    fundamentals: edgar.Fundamentals
    metrics: Dict[str, DataPoint]
    quote: Optional[DataPoint]
    news: List[dict]
    disclosure: Optional[stockact.DisclosureSignal]
    etf_info: object = None


def gather(ticker: str, asset_type_hint: Optional[str] = None) -> TickerData:
    ticker = ticker.strip().upper()
    if not ticker or not ticker.replace(".", "").replace("-", "").isalnum():
        raise InsufficientData(ticker, "El símbolo no parece válido.", [])

    asset_type = guess_asset_type(ticker, asset_type_hint)
    etf_info = lookup_etf(ticker)

    try:
        series = prices.fetch_daily(ticker)
    except FetchError as exc:
        raise InsufficientData(
            ticker,
            f"No se pudo obtener ningún precio de {ticker}. Sin precio no hay análisis "
            f"posible, y prefiero decírtelo a inventar algo. Detalle: {exc}",
            [prices.PROVIDERS[k][0] for k in prices.order()],
        ) from exc

    fundamentals = edgar.fetch_fundamentals(ticker, asset_type)
    metrics = finnhub.fetch_metrics(ticker) if finnhub.enabled() else {}
    quote = finnhub.fetch_quote(ticker) if finnhub.enabled() else None

    news_items = [n.to_dict() for n in news_rss.fetch_news(ticker, fundamentals.cik, limit=8)]
    if finnhub.enabled():
        news_items = (finnhub.fetch_company_news(ticker) + news_items)[:10]

    # Para un ETF manda el nombre del catálogo; EDGAR no describe fondos. Para una
    # acción manda el nombre que la propia empresa registra en la SEC.
    name = (etf_info.name if etf_info else "") or fundamentals.company_name or ticker

    return TickerData(
        ticker=ticker,
        asset_type=asset_type,
        name=name,
        series=series,
        fundamentals=fundamentals,
        metrics=metrics,
        quote=quote,
        news=news_items,
        disclosure=stockact.fetch_signal(ticker),
        etf_info=etf_info,
    )


# ---------------------------------------------------------------------------
# Puntuación
# ---------------------------------------------------------------------------
def _score_trend(data: TickerData) -> Tuple[float, str, List[Datum]]:
    d200 = ind.pct_vs_sma(data.series, 200)
    d50 = ind.pct_vs_sma(data.series, 50)
    points: List[Datum] = [d200, d50]
    score = 0.0
    if isinstance(d200, DataPoint):
        score += max(-20.0, min(20.0, d200.value * 0.8))
    if isinstance(d50, DataPoint):
        score += max(-10.0, min(10.0, d50.value * 0.6))
    label = ind.trend_label(data.series)
    return score, f"Tendencia {label} respecto a sus medias de 50 y 200 días.", points


def _score_volatility(data: TickerData, profile: Profile) -> Tuple[float, str, List[Datum]]:
    vol = ind.annualized_volatility(data.series)
    ceiling = volatility_ceiling(profile)
    if not isinstance(vol, DataPoint):
        return 0.0, "No hay historia suficiente para medir la volatilidad.", [vol]
    src = user_source()
    ceiling_dp = DataPoint(
        label="Volatilidad máxima cómoda para tu perfil",
        value=ceiling,
        unit="%",
        as_of=profile.updated_at or date.today(),
        source=src,
        precision=1,
    )
    if vol.value > ceiling * 1.5:
        return -20.0, "Se mueve mucho más de lo que encaja con tu tolerancia al riesgo.", [vol, ceiling_dp]
    if vol.value > ceiling:
        return -10.0, "Se mueve algo más de lo que encaja con tu tolerancia al riesgo.", [vol, ceiling_dp]
    return 8.0, "Su nivel de oscilación entra dentro de lo que declaraste tolerar.", [vol, ceiling_dp]


def _score_drawdown(data: TickerData) -> Tuple[float, str, List[Datum]]:
    dd = ind.drawdown_from_high(data.series)
    if not isinstance(dd, DataPoint):
        return 0.0, "No hay ventana de 52 semanas para medir la caída desde máximos.", [dd]
    # Una caída moderada puede ser mejor punto de entrada; una caída severa
    # suele significar que el mercado ve un problema real.
    if dd.value <= -50:
        return -12.0, "Está muy por debajo de su máximo de 52 semanas, lo que suele señalar un problema de fondo, no una ganga.", [dd]
    if dd.value <= -20:
        return 8.0, "Cotiza claramente por debajo de su máximo de 52 semanas.", [dd]
    if dd.value >= -3:
        return -4.0, "Está prácticamente en su máximo de 52 semanas.", [dd]
    return 3.0, "Está algo por debajo de su máximo de 52 semanas.", [dd]


def _score_fundamentals(data: TickerData) -> Tuple[float, str, List[Datum]]:
    if data.asset_type == "etf":
        return (
            0.0,
            "Es un ETF: no tiene fundamentales propios que analizar. Lo relevante es qué "
            "replica, cuán diversificado está y cuánto cobra de comisión.",
            [Missing(
                label="Fundamentales de empresa",
                reason=data.fundamentals.unavailable_reason or "No aplica a un ETF.",
                tried="SEC EDGAR",
            )],
        )

    f = data.fundamentals
    points: List[Datum] = []
    score = 0.0
    notes: List[str] = []

    revenue = f.datapoint("revenue", "Ingresos anuales", "USD", precision=0)
    net_income = f.datapoint("net_income", "Beneficio neto anual", "USD", precision=0)
    points.extend([revenue, net_income])

    # Rentabilidad: ¿gana dinero?
    if isinstance(net_income, DataPoint):
        if net_income.value > 0:
            score += 10.0
            notes.append("La empresa reportó beneficio en su último ejercicio anual")
        else:
            score -= 12.0
            notes.append("La empresa reportó pérdidas en su último ejercicio anual")

    # Margen neto derivado de dos datos citados.
    if isinstance(revenue, DataPoint) and isinstance(net_income, DataPoint) and revenue.value > 0:
        margin = net_income.value / revenue.value * 100.0
        points.append(
            DataPoint(
                label="Margen neto (beneficio sobre ingresos)",
                value=margin,
                unit="%",
                as_of=revenue.as_of,
                source=derived_source([f.source], "beneficio neto / ingresos"),
                precision=1,
            )
        )
        if margin > 15:
            score += 8.0
            notes.append("con un margen neto holgado")
        elif margin < 0:
            score -= 5.0

    # Crecimiento de ingresos interanual (dos ejercicios citados).
    prev_rev = f.previous.get("revenue")
    cur_rev = f.latest.get("revenue")
    if prev_rev and cur_rev and prev_rev.value > 0:
        growth = (cur_rev.value / prev_rev.value - 1.0) * 100.0
        points.append(
            DataPoint(
                label="Crecimiento de ingresos frente al ejercicio anterior",
                value=growth,
                unit="%",
                as_of=cur_rev.period_end,
                source=derived_source([f.source], "ingresos año actual / año anterior"),
                precision=1,
            )
        )
        if growth > 10:
            score += 8.0
            notes.append("y los ingresos creciendo")
        elif growth < -5:
            score -= 8.0
            notes.append("y los ingresos cayendo")

    # Endeudamiento.
    equity = f.latest.get("equity")
    liabilities = f.latest.get("liabilities")
    if equity and liabilities and equity.value > 0:
        ratio = liabilities.value / equity.value
        points.append(
            DataPoint(
                label="Pasivos sobre patrimonio (cuánto debe frente a lo que tiene)",
                value=ratio,
                unit="x",
                as_of=equity.period_end,
                source=derived_source([f.source], "pasivos totales / patrimonio neto"),
                precision=2,
            )
        )
        if ratio > 3:
            score -= 8.0
            notes.append("aunque con un endeudamiento alto")

    # PER, si Finnhub está activo.
    per = data.metrics.get("peBasicExclExtraTTM") or data.metrics.get("peNormalizedAnnual")
    if per is not None:
        points.append(per)
        if 0 < per.value < 18:
            score += 6.0
        elif per.value > 45:
            score -= 8.0
            notes.append("y una valoración exigente frente a sus beneficios")

    if not notes:
        notes.append("Los fundamentales disponibles no dibujan una señal clara")

    return score, ". ".join(notes) + ".", points


def _score_portfolio_fit(
    data: TickerData, state: PortfolioState, profile: Profile, strategy: Strategy
) -> Tuple[float, str, List[Datum]]:
    points: List[Datum] = []
    src = user_source()
    today = date.today()
    score = 0.0
    notes: List[str] = []

    total = state.total_value
    if not total:
        return (
            0.0,
            "Todavía no has registrado cartera, así que no puedo juzgar el encaje. "
            "Registra tus posiciones y tu efectivo y volveré a mirarlo.",
            [Missing(label="Cartera registrada", reason="No hay posiciones ni efectivo registrados.")],
        )

    weights = state.weights()
    current_weight = weights.get(data.ticker, 0.0)
    points.append(
        DataPoint(
            label=f"Peso actual de {data.ticker} en tu cartera",
            value=current_weight,
            unit="%",
            as_of=today,
            source=src,
            precision=2,
        )
    )

    cap = position_cap(data.ticker, data.asset_type, strategy)
    if cap < NO_CAP:
        points.append(
            DataPoint(
                label="Tope por posición que fija tu estrategia",
                value=cap,
                unit="%",
                as_of=profile.updated_at or today,
                source=src,
                precision=1,
            )
        )

    if cap < NO_CAP and current_weight >= cap:
        score -= 20.0
        notes.append(
            f"Ya tienes en {data.ticker} tanto o más de lo que tu propia estrategia marca "
            f"como tope, así que añadir más iría en contra de tu plan"
        )
    elif current_weight > 0:
        notes.append(
            f"Ya tienes algo de {data.ticker}. {cap_explanation(data.ticker, data.asset_type)}"
        )
    else:
        notes.append(f"No tienes {data.ticker} en cartera")

    # Solapamiento sectorial.
    sector = sector_of(data.ticker, data.asset_type)
    sector_weight = state.sector_weights().get(sector, 0.0)
    if sector not in ("Diversificado (ETF)", "Bonos", "Desconocido"):
        points.append(
            DataPoint(
                label=f"Peso del sector {sector} en tu cartera",
                value=sector_weight,
                unit="%",
                as_of=today,
                source=src,
                precision=2,
            )
        )
        if sector_weight > strategy.max_sector_pct:
            score -= 12.0
            notes.append(f"y el sector {sector} ya pesa por encima de tu tope")
        elif sector_weight < 5.0:
            score += 5.0
            notes.append(f"y añadiría exposición a un sector donde apenas tienes nada")

    # Diversificación por número de posiciones.
    if data.ticker not in weights and data.asset_type == "etf" and is_broad_etf(data.ticker):
        score += 10.0
        notes.append("y un ETF amplio aporta diversificación en un solo paso")

    # Efectivo disponible.
    points.append(
        DataPoint(
            label="Efectivo disponible",
            value=state.cash,
            unit="USD",
            as_of=state.cash_updated or today,
            source=src,
        )
    )
    if state.cash <= 0:
        score -= 10.0
        notes.append("aunque ahora mismo no tienes efectivo registrado para comprar nada")

    # Bonos: si la cartera va corta de bonos frente al objetivo, un ETF de bonos suma.
    mix = state.stocks_vs_bonds()
    etf_info = data.etf_info
    if etf_info is not None and getattr(etf_info, "asset_class", "") == "bonos":
        if mix["bonos"] is not None and mix["bonos"] < strategy.target_bonds_pct - 5:
            score += 12.0
            notes.append("y tu cartera va corta de bonos frente a tu objetivo")

    return score, ". ".join(notes) + ".", points


def _score_profile_fit(data: TickerData, profile: Profile) -> Tuple[float, str, List[Datum]]:
    """Encaje con tu perfil, con el sesgo de principiante hecho explícito.

    La regla «para un principiante, sesga hacia ETFs amplios antes que acciones
    individuales de moda» vive aquí y no escondida en otro factor, para que
    puedas verla en el desglose de la puntuación y discutirla.
    """
    src = user_source()
    today = date.today()
    points: List[Datum] = [
        DataPoint(
            label="Tu horizonte de inversión",
            value=profile.horizon_years,
            unit="años",
            as_of=profile.updated_at or today,
            source=src,
            precision=0,
        )
    ]

    beginner = profile.experience == "principiante"
    broad = data.asset_type == "etf" and is_broad_etf(data.ticker)

    if broad:
        score = 12.0 if beginner else 6.0
        note = (
            "Es un fondo amplio y diversificado, que es el tipo de activo hacia el que esta "
            "herramienta te inclina mientras estés empezando."
        )
    elif data.asset_type == "etf":
        score = 0.0
        note = (
            "Es un ETF, pero no de los amplios: concentra en un tipo de empresa, así que no "
            "cuenta como la base diversificada de una cartera."
        )
    else:
        score = -8.0 if beginner else -2.0
        note = (
            "Es una acción individual. Para quien empieza, acertar con empresas concretas es "
            "difícil incluso para profesionales, así que pesa en contra frente a un fondo amplio."
        )

    # Horizonte corto y activo volátil no casan bien.
    vol = ind.annualized_volatility(data.series)
    if profile.horizon_years <= 3 and isinstance(vol, DataPoint) and vol.value > 15:
        score -= 10.0
        note += (
            " Además, tu horizonte es corto y este activo oscila lo suficiente como para que "
            "una caída te pille sin tiempo de recuperarte."
        )

    return score, note, points


def _sentiment(data: TickerData) -> Optional[dict]:
    """Sentimiento de mercado: sólo si hay dato real. Si no, se declara ausente."""
    beta = data.metrics.get("beta")
    if beta is None:
        return None
    return {
        "available": True,
        "note": (
            "No hay un índice de sentimiento propiamente dicho en las fuentes gratuitas "
            "que usa esta herramienta. Lo más cercano que sí es un dato real es la beta: "
            "cuánto tiende a moverse este activo cuando se mueve el mercado."
        ),
        "beta": beta.to_dict(),
    }


# ---------------------------------------------------------------------------
# Construcción de la recomendación
# ---------------------------------------------------------------------------
def _decide(score: float, held: bool, at_cap: bool) -> Tuple[str, str]:
    if held:
        if score <= -30:
            return "vender", "Considerar vender"
        if score >= 30 and not at_cap:
            return "comprar", "Considerar añadir un poco más"
        return "mantener", "Mantener lo que tienes, sin tocar nada"
    if score >= 25 and not at_cap:
        return "comprar", "Candidato razonable a compra"
    if score <= -20:
        return "evitar", "Mejor evitarlo por ahora"
    return "evitar", "Ni comprar ni descartar: déjalo en observación"


def _position_sizing(
    data: TickerData,
    state: PortfolioState,
    profile: Profile,
    strategy: Strategy,
    action: str,
    last_price: DataPoint,
) -> dict:
    today = date.today()
    src = user_source()

    if action not in ("comprar",):
        return {
            "applies": False,
            "explanation": (
                "No procede sugerir tamaño de posición porque la idea no es comprar."
            ),
            "data": [],
        }

    cap = position_cap(data.ticker, data.asset_type, strategy)
    current = state.weights().get(data.ticker, 0.0)
    room_pct = max(0.0, cap - current)

    total = state.total_value or 0.0
    room_usd = room_pct / 100.0 * total

    # Tu propia estrategia fija un mínimo de efectivo. Sugerir gastar hasta el
    # último dólar lo incumpliría: te dejaría sin margen y contradiría el plan
    # que la herramienta dice estar siguiendo.
    reserve = strategy.min_cash_pct / 100.0 * total
    investable_cash = max(0.0, state.cash - reserve)
    budget = min(room_usd, investable_cash)

    data_points: List[Datum] = []
    if cap < NO_CAP:
        data_points += [
            DataPoint(label="Tope por posición de tu estrategia", value=cap, unit="%",
                      as_of=profile.updated_at or today, source=src, precision=1),
            DataPoint(label="Margen que te queda hasta el tope", value=room_pct, unit="%",
                      as_of=today, source=src, precision=2),
        ]
    data_points.append(
        DataPoint(label="Efectivo disponible", value=state.cash, unit="USD",
                  as_of=state.cash_updated or today, source=src)
    )
    if reserve > 0:
        data_points.append(
            DataPoint(label="Colchón de efectivo que reserva tu estrategia", value=reserve,
                      unit="USD", as_of=profile.updated_at or today, source=src)
        )

    if budget <= 0:
        explanation = (
            "El tamaño sugerido es cero por ahora: o no queda margen hasta el tope que "
            "fijaste para una sola posición, o el efectivo que tienes está comprometido con "
            "el colchón mínimo de tu estrategia. Tu aporte mensual es la vía natural para "
            "entrar sin forzar nada."
        )
        if profile.monthly_contribution > 0:
            data_points.append(
                DataPoint(label="Tu aporte mensual", value=profile.monthly_contribution,
                          unit="USD", as_of=profile.updated_at or today, source=src)
            )
        return {"applies": True, "amount_usd": 0.0, "pct_of_portfolio": 0.0,
                "approx_shares": 0.0, "explanation": explanation,
                "data": [d.to_dict(today) for d in data_points]}

    shares = budget / last_price.value if last_price.value > 0 else 0.0
    data_points.append(
        DataPoint(label="Importe sugerido", value=budget, unit="USD", as_of=today,
                  source=user_source())
    )
    data_points.append(last_price)

    limit_reason = (
        "es lo que cabe hasta el tope por posición que fijaste, limitado por el efectivo "
        "que tienes disponible una vez apartado el colchón que pide tu estrategia"
        if cap < NO_CAP
        else "es el efectivo que te queda tras apartar el colchón que pide tu estrategia, ya "
             "que a un ETF amplio no se le aplica tope por posición"
    )
    explanation = (
        f"El importe sale de tu propio plan, no de una corazonada: {limit_reason}. "
        f"Nada te obliga a poner todo de una vez; repartir la entrada en varios aportes "
        f"mensuales reduce el riesgo de comprar justo en un mal día."
    )

    return {
        "applies": True,
        "amount_usd": round(budget, 2),
        "pct_of_portfolio": round(budget / total * 100.0, 2) if total else None,
        "approx_shares": round(shares, 4),
        "explanation": explanation,
        "data": [d.to_dict(today) for d in data_points],
    }


def is_bond_fund(data: TickerData) -> bool:
    return getattr(data.etf_info, "asset_class", "") == "bonos"


def describe_asset(data: TickerData) -> str:
    """Qué es esto, en una frase y sin jerga. Un fondo de bonos NO compra empresas."""
    if data.asset_type != "etf":
        return "una empresa concreta que cotiza en bolsa"
    if is_bond_fund(data):
        return (
            "un fondo cotizado de bonos, es decir, una cesta de préstamos a gobiernos y "
            "empresas que pagan intereses"
        )
    if is_broad_etf(data.ticker):
        return "un fondo cotizado que compra muchísimas empresas a la vez"
    return "un fondo cotizado centrado en un tipo concreto de empresa"


def _build_risks(
    data: TickerData, profile: Profile, state: PortfolioState, strategy: Strategy
) -> List[str]:
    """Riesgos concretos. Siempre hay al menos uno: invertir siempre tiene riesgo."""
    risks: List[str] = []

    if data.asset_type == "etf":
        if is_bond_fund(data):
            risks.append(
                "Los bonos no son dinero en efectivo: cuando suben los tipos de interés, los "
                "bonos que ya existen valen menos, y un fondo de bonos puede perder valor "
                "durante meses o años."
            )
            risks.append(
                "Quien emitió el bono puede dejar de pagar. Un fondo reparte ese riesgo entre "
                "muchos emisores, pero no lo elimina."
            )
        else:
            risks.append(
                "Un ETF amplio baja el riesgo de equivocarte con una empresa, pero no te "
                "protege de una caída general del mercado: si cae todo, cae contigo."
            )
            info = data.etf_info
            if info is not None and getattr(info, "breadth", "") in ("sectorial", "tematico"):
                risks.append(
                    "Este ETF no es un índice amplio: concentra su apuesta en un tipo de "
                    "empresa. Puede comportarse muy distinto del mercado en conjunto, para "
                    "bien y para mal."
                )
        risks.append(
            "El ratio de gastos del fondo se descuenta todos los años aunque el fondo "
            "pierda. Compruébalo en la ficha oficial del emisor antes de comprar."
        )
    else:
        risks.append(
            "Es una sola empresa. Puede caer mucho por algo específico suyo (un mal "
            "trimestre, un pleito, un cambio de dirección) y no recuperarse nunca, aunque "
            "el mercado en general suba."
        )

    vol = ind.annualized_volatility(data.series)
    if isinstance(vol, DataPoint) and vol.value > volatility_ceiling(profile):
        risks.append(
            "Este activo oscila más de lo que declaraste tolerar. El riesgo real no es que "
            "baje, sino que te asustes en una caída y vendas justo en el peor momento."
        )

    dd = ind.drawdown_from_high(data.series)
    if isinstance(dd, DataPoint) and dd.value <= -30:
        risks.append(
            "Está bastante por debajo de su máximo de 52 semanas. Un precio más bajo que "
            "antes no significa barato: puede que el mercado esté descontando un deterioro real."
        )

    if data.asset_type != "etf" and not data.fundamentals.latest:
        risks.append(
            "No he podido leer fundamentales de esta empresa en la SEC, así que la parte "
            "de negocio de este análisis está a ciegas: sólo estoy viendo precio."
        )

    cap = position_cap(data.ticker, data.asset_type, strategy)
    current = state.weights().get(data.ticker, 0.0)
    if current >= cap * 0.8:
        risks.append(
            "Tu exposición a este activo ya se acerca al tope que tú mismo fijaste. "
            "Concentrar más aumenta cuánto te duele si esto sale mal."
        )

    risks.append(
        "Invertir desde Perú en un bróker extranjero tiene consecuencias tributarias "
        "propias que esta herramienta no calcula. Consúltalas con un contador."
    )
    return risks


def _build_counter_argument(data: TickerData, action: str, score: float) -> str:
    """El contra-caso más fuerte. Obligatorio: sin esto no se muestra nada."""
    trend = ind.trend_label(data.series)

    if action == "comprar":
        base = (
            "El argumento más fuerte en contra es que esta lectura se apoya sobre todo en "
            "que el precio viene comportándose bien, y el comportamiento pasado del precio "
            "no predice el futuro: comprar algo porque ha subido es exactamente cómo se "
            "compra caro. "
        )
        if data.asset_type != "etf":
            base += (
                "Además, todo lo que yo puedo leer en los estados financieros ya lo han "
                "leído miles de analistas profesionales con más datos y más rapidez, así "
                "que es probable que ya esté reflejado en el precio. Si esta idea fuese "
                "tan clara, no estaría disponible."
            )
        else:
            base += (
                "Y si tu cartera ya tiene un ETF amplio parecido, añadir otro no te "
                "diversifica más: te da la misma exposición dos veces con más comisiones "
                "y más cosas que vigilar."
            )
        return base

    if action == "vender":
        return (
            "El argumento más fuerte en contra de vender es que vender tras una caída "
            "convierte una pérdida temporal en una pérdida definitiva, y la historia está "
            "llena de activos que se recuperaron justo después de que los inversores "
            "impacientes se rindieran. Vender también tiene coste fiscal y de oportunidad, "
            "y ninguna de las señales que veo distingue un deterioro permanente de un mal "
            "momento pasajero."
        )

    if action == "mantener":
        return (
            "El argumento más fuerte en contra de no hacer nada es que la inacción también "
            "es una decisión: si este activo ya no encaja con tu plan, mantenerlo por "
            "inercia es asumir un riesgo que no elegiste conscientemente. Y si estuviese "
            "realmente barato, esperar te cuesta rentabilidad."
        )

    return (
        f"El argumento más fuerte en contra de descartarlo es que mi lectura es mecánica y "
        f"mira sobre todo precio y cifras contables pasadas. Una tendencia {trend} puede "
        f"reflejar un problema temporal ya resuelto, o un cambio de negocio que las cuentas "
        f"del año pasado todavía no muestran. Descartar algo por sus números de ayer es una "
        f"forma habitual de perderse buenas ideas."
    )


def _beginner_warnings(
    data: TickerData, profile: Profile, state: PortfolioState, strategy: Strategy, action: str
) -> List[str]:
    warnings: List[str] = []
    if profile.experience != "principiante":
        return warnings

    if data.asset_type != "etf" and action == "comprar":
        warnings.append(
            "Estás mirando una empresa concreta. Para alguien que empieza, lo habitual es "
            "que el grueso de la cartera esté en ETFs que compran cientos de empresas a la "
            "vez, y que las apuestas individuales sean una porción pequeña con la que "
            "aprender sin jugarte el plan."
        )

    if data.asset_type == "etf" and not is_broad_etf(data.ticker):
        warnings.append(
            "Este ETF no es de los amplios: concentra en un tipo de empresa. Se parece más "
            "a una apuesta sectorial que a la base diversificada de una cartera."
        )

    indiv = state.individual_stock_pct()
    if data.asset_type != "etf" and indiv > 15:
        warnings.append(
            "Una parte notable de tu cartera ya está en acciones individuales. Sumar otra "
            "aumenta la probabilidad de que tu resultado dependa de aciertos concretos en "
            "vez de del mercado en conjunto."
        )

    if not profile.emergency_fund_ok:
        warnings.append(
            "Declaraste no tener fondo de emergencia. Antes de invertir más, tener unos "
            "meses de gastos guardados aparte evita que un imprevisto te obligue a vender "
            "en el peor momento."
        )
    return warnings


def _confidence(data: TickerData, today: date) -> Tuple[str, List[str], List[str]]:
    basis: List[str] = []
    gaps: List[str] = []
    points = 0

    last = data.series.last
    age = (today - last.day).days
    if age <= STALE_PRICE_DAYS:
        basis.append(
            f"Precio de cierre reciente de {data.series.source.name} (dato al "
            f"{last.day.isoformat()})."
        )
        points += 2
    else:
        gaps.append(
            f"El último cierre disponible es del {last.day.isoformat()}, hace {age} días. "
            f"Puede que el mercado haya estado cerrado, o que la fuente vaya con retraso."
        )
        points += 1

    history = len(data.series.bars)
    if history >= 500:
        basis.append("Más de dos años de historia de precios para medir tendencia y volatilidad.")
        points += 2
    elif history >= 200:
        basis.append("Cerca de un año de historia de precios.")
        points += 1
    else:
        gaps.append(
            f"Sólo hay {history} sesiones de historia. Las medias largas y la volatilidad "
            f"pierden significado con series tan cortas."
        )

    if data.asset_type == "etf":
        basis.append("Es un ETF: el análisis se apoya en precio, diversificación y encaje, no en fundamentales.")
        gaps.append(
            "El ratio de gastos y la composición exacta del fondo no están en las fuentes "
            "gratuitas: consúltalos en la ficha oficial del emisor."
        )
        points += 1
    elif data.fundamentals.latest:
        basis.append(
            f"Fundamentales anuales leídos directamente de SEC EDGAR (la fuente original, "
            f"no una estimación de terceros)."
        )
        points += 2
    else:
        gaps.append(
            data.fundamentals.unavailable_reason
            or "No hay fundamentales disponibles para este símbolo."
        )

    if data.metrics:
        basis.append("Ratios de mercado de Finnhub (clave gratuita activa).")
        points += 1
    else:
        gaps.append(
            "Sin clave de Finnhub configurada: no hay PER ni beta ni ratios ya calculados. "
            "Se puede activar con la variable de entorno FINNHUB_API_KEY."
        )

    if data.news:
        basis.append("Titulares recientes citados con su fuente y su fecha.")
    else:
        gaps.append("No se encontraron titulares recientes para este símbolo.")

    gaps.append(
        "No hay un índice de sentimiento de mercado en las fuentes gratuitas, así que ese "
        "frente del análisis está ausente y no se ha sustituido por nada inventado."
    )

    level = "alta" if points >= 7 else ("media" if points >= 4 else "baja")
    return level, basis, gaps


def analyze(
    ticker: str,
    profile: Profile,
    strategy: Strategy,
    state: PortfolioState,
    asset_type_hint: Optional[str] = None,
    today: Optional[date] = None,
    user_facts: Optional[List[DataPoint]] = None,
) -> Recommendation:
    """Análisis completo de un ticker. Lanza ``InsufficientData`` si no hay precio.

    ``user_facts`` son datos que tú leíste en una fuente oficial y registraste
    (típicamente el ratio de gastos de un ETF). Se tratan como datos citados
    con fuente "lo que tú leíste" y la fecha en que lo leíste.
    """
    today = today or date.today()
    data = gather(ticker, asset_type_hint)

    last_price = ind.last_close(data.series)

    trend_s, trend_note, trend_pts = _score_trend(data)
    vol_s, vol_note, vol_pts = _score_volatility(data, profile)
    dd_s, dd_note, dd_pts = _score_drawdown(data)
    fund_s, fund_note, fund_pts = _score_fundamentals(data)
    fit_s, fit_note, fit_pts = _score_portfolio_fit(data, state, profile, strategy)
    prof_s, prof_note, prof_pts = _score_profile_fit(data, profile)

    score = trend_s + vol_s + dd_s + fund_s + fit_s + prof_s

    breakdown = [
        {"factor": "Tendencia de precio", "points": round(trend_s, 1), "note": trend_note},
        {"factor": "Volatilidad frente a tu perfil", "points": round(vol_s, 1), "note": vol_note},
        {"factor": "Posición frente a máximos", "points": round(dd_s, 1), "note": dd_note},
        {"factor": "Fundamentales", "points": round(fund_s, 1), "note": fund_note},
        {"factor": "Encaje con tu cartera", "points": round(fit_s, 1), "note": fit_note},
        {"factor": "Encaje con tu perfil", "points": round(prof_s, 1), "note": prof_note},
    ]

    cap = position_cap(data.ticker, data.asset_type, strategy)
    current_weight = state.weights().get(data.ticker, 0.0)
    held = current_weight > 0
    at_cap = current_weight >= cap

    action, action_label = _decide(score, held, at_cap)

    # Freno de principiante: no proponer comprar una acción individual cuando
    # la cartera ya está muy cargada de ellas.
    if (
        action == "comprar"
        and data.asset_type != "etf"
        and profile.experience == "principiante"
        and state.individual_stock_pct() > 25
    ):
        action, action_label = "evitar", "Mejor no ahora: ya dependes mucho de acciones sueltas"

    # --- Evidencia --------------------------------------------------------
    evidence: List[Evidence] = [
        Evidence(claim="Precio de referencia usado en todo el análisis.", data=[last_price], kind="precio"),
        Evidence(claim=trend_note, data=trend_pts, kind="precio"),
        Evidence(claim=dd_note, data=dd_pts, kind="precio"),
        Evidence(claim=vol_note, data=vol_pts, kind="precio"),
        Evidence(claim=fund_note, data=fund_pts, kind="fundamental"),
        Evidence(claim=fit_note, data=fit_pts, kind="cartera"),
        Evidence(claim=prof_note, data=prof_pts, kind="perfil"),
    ]

    ret_1y = ind.total_return(data.series, 252, "Variación del precio en el último año")
    ret_3m = ind.total_return(data.series, 63, "Variación del precio en los últimos tres meses")
    evidence.append(
        Evidence(
            claim="Cómo se ha comportado el precio en el último año y en los últimos meses.",
            data=[ret_1y, ret_3m],
            kind="precio",
        )
    )

    if data.quote is not None:
        evidence.append(
            Evidence(
                claim="Cotización más fresca que el cierre diario, cuando la clave de Finnhub está activa.",
                data=[data.quote],
                kind="precio",
            )
        )

    if data.asset_type == "etf" and data.etf_info is not None:
        info = data.etf_info
        registered = [f for f in (user_facts or []) if f.label.startswith("Ratio de gastos")]
        cost_datum: Datum = registered[0] if registered else Missing(
            label="Ratio de gastos del fondo",
            reason=(
                "Ninguna fuente gratuita lo publica de forma fiable, y escribirlo de memoria "
                "sería inventarlo. Léelo en la ficha oficial del emisor y regístralo: entonces "
                "aparecerá aquí citado con la fecha en que lo leíste."
            ),
            tried="Stooq, SEC EDGAR, Finnhub",
        )
        evidence.append(
            Evidence(
                claim=(
                    f"{info.name}, emitido por {info.issuer}. {info.exposure} "
                    f"La comisión anual del fondo se descuenta de tu rentabilidad todos los años, "
                    f"así que conviene conocerla antes de comprar."
                ),
                data=[cost_datum],
                kind="fundamental",
            )
        )

    for fact in user_facts or []:
        if fact.label.startswith("Ratio de gastos") and data.asset_type == "etf":
            continue  # ya mostrado arriba
        evidence.append(
            Evidence(
                claim="Dato que registraste tú desde una fuente oficial.",
                data=[fact],
                kind="fundamental",
            )
        )

    # --- Tesis (sin cifras, en lenguaje simple) ---------------------------
    trend_word = ind.trend_label(data.series)
    what_is = describe_asset(data)
    thesis_map = {
        "comprar": (
            f"{data.ticker} es {what_is}, con una tendencia de precio {trend_word} y un encaje "
            f"razonable con el plan que definiste. La idea es entrar poco a poco, dentro del "
            f"tope que tú mismo fijaste, no de golpe."
        ),
        "mantener": (
            f"{data.ticker} es {what_is}. Con lo que veo hoy no hay motivo suficiente ni para "
            f"comprar más ni para vender: lo sensato es dejarlo estar y seguir con tus aportes "
            f"según el plan."
        ),
        "vender": (
            f"{data.ticker} es {what_is}, y varias señales apuntan a que ha dejado de encajar "
            f"con tu plan. Vale la pena revisar si sigue teniendo un sitio en tu cartera, sin "
            f"prisa y mirando también el coste fiscal de deshacer la posición."
        ),
        "evitar": (
            f"{data.ticker} es {what_is}. Hoy no reúne condiciones suficientes para entrar según "
            f"tus propios criterios. No es un juicio definitivo sobre el activo: es que ahora "
            f"mismo no encaja. Déjalo en la watchlist y vuelve a mirarlo más adelante."
        ),
    }
    thesis = thesis_map[action]

    risks = _build_risks(data, profile, state, strategy)
    counter = _build_counter_argument(data, action, score)
    conf_level, conf_basis, gaps = _confidence(data, today)
    warnings = _beginner_warnings(data, profile, state, strategy, action)
    sizing = _position_sizing(data, state, profile, strategy, action, last_price)

    context: List[dict] = []
    if data.disclosure is not None:
        context.append(
            {
                "kind": "stock_act",
                "title": "Divulgaciones del Congreso de EE. UU. sobre este ticker",
                **data.disclosure.to_dict(),
            }
        )

    rec = Recommendation(
        ticker=data.ticker,
        name=data.name,
        asset_type=data.asset_type,
        action=action,
        action_label=action_label,
        thesis=thesis,
        suggested_position=sizing,
        evidence=evidence,
        risks=risks,
        counter_argument=counter,
        portfolio_fit=fit_note,
        portfolio_fit_data=fit_pts,
        confidence_level=conf_level,
        confidence_basis=conf_basis,
        data_gaps=gaps,
        news=data.news,
        sentiment=_sentiment(data),
        context_signals=context,
        beginner_warnings=warnings,
        score=score,
        score_breakdown=breakdown,
        as_of=today,
    )

    enforce_hard_rules(rec)
    return rec


def enforce_hard_rules(rec: Recommendation) -> None:
    """Aplica las reglas duras. Si algo falla, la recomendación NO se muestra."""
    assert_recommendation_complete(
        thesis=rec.thesis,
        risks=rec.risks,
        counter_argument=rec.counter_argument,
        confidence_basis=rec.confidence_basis,
        portfolio_fit=rec.portfolio_fit,
    )

    allowed = collect_allowed_numbers(rec.all_data())

    prose: List[Tuple[str, str]] = [
        (rec.thesis, "tesis"),
        (rec.counter_argument, "contra-argumento"),
        (rec.portfolio_fit, "encaje con la cartera"),
        (rec.suggested_position.get("explanation", ""), "tamaño de posición"),
    ]
    prose += [(r, f"riesgo #{i + 1}") for i, r in enumerate(rec.risks)]
    prose += [(w, f"aviso de principiante #{i + 1}") for i, w in enumerate(rec.beginner_warnings)]
    prose += [(e.claim, f"evidencia «{e.kind}»") for e in rec.evidence]
    prose += [(b["note"], f"desglose «{b['factor']}»") for b in rec.score_breakdown]

    for text, where in prose:
        assert_numbers_are_cited(text, allowed, where)
        assert_no_pressure_language(text, where)
