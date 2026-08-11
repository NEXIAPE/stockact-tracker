"""
«Más barato que hace poco»: qué de lo tuyo cotiza por debajo de su máximo.

POR QUÉ NO SE LLAMA «OPORTUNIDADES»
La petición original era «cosas que caen y se sabe que volverán a subir». Eso
no se sabe, de ningún activo, nunca. Una caída y un negocio rompiéndose se ven
idénticos desde fuera: cuando Kodak cayó un 30 % parecía una ganga. Llamar
«oportunidad» a un precio más bajo es afirmar la conclusión antes de mirar, y
es el error que más caro le sale a quien empieza.

Así que esta pantalla dice UN SOLO HECHO comprobable —esto cotiza un X % por
debajo de su máximo de 52 semanas— y deja la conclusión abierta. No hay
estimaciones de recuperación, ni objetivos de precio, ni «suele rebotar». Eso
serían números inventados, que es la regla dura número uno.

POR QUÉ SE SEPARAN ETFS AMPLIOS Y ACCIONES SUELTAS
Porque una caída significa cosas distintas en cada caso, y mezclarlas es la
trampa entera:

  * Un ETF amplio que baja es el MISMO conjunto de miles de empresas, más
    barato. No es que vaya a recuperarse —eso sigue sin saberse—, es que si el
    mercado mundial entero no se recupera jamás, la cartera es el menor de los
    problemas.
  * Una acción suelta que baja puede ser una ganga o el principio del final, y
    esta herramienta NO puede distinguirlo. Se muestra, pero con esa frase
    delante.

POR QUÉ NO ES UN ESCÁNER DE TODO EL MERCADO
Sólo mira lo que ya está en tu universo: tu watchlist, el núcleo diversificado
y lo que ya tienes. Una lista de «lo que más ha caído hoy» en todo el mercado
es literalmente una lista de cuchillos cayendo, y sería el descubrimiento
diario que el resto de la herramienta evita a propósito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from ..providers import news_rss, prices
from ..providers.stooq import FetchError
from . import indicators as ind
from .datapoint import DataPoint, Datum
from .ideas import candidate_tickers
from .portfolio import PortfolioState
from .profile import Profile, Strategy
from .universe import is_broad_etf, lookup_etf

# Umbral para aparecer. Un 10 % es la marca habitual de «corrección» y evita
# llenar la pantalla de ruido: un 2 % abajo no es noticia, es un martes.
THRESHOLD_PCT = -10.0

# A partir de aquí, en una acción suelta, la caída deja de sugerir mejor precio
# y empieza a sugerir que el mercado ve un problema real. El motor de
# recomendación ya penaliza en ese tramo; aquí se dice con palabras.
DEEP_PCT = -30.0

MAX_TICKERS = 8
NEWS_PER_TICKER = 4


@dataclass
class Fallen:
    ticker: str
    name: str
    is_broad: bool
    asset_type: str
    held: bool
    drawdown: DataPoint
    last_close: DataPoint
    high_52w: Datum
    news: List[dict] = field(default_factory=list)
    reading: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self, today: date) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "is_broad": self.is_broad,
            "asset_type": self.asset_type,
            "held": self.held,
            "drawdown": self.drawdown.to_dict(today),
            "last_close": self.last_close.to_dict(today),
            "high_52w": self.high_52w.to_dict(today),
            "news": self.news,
            "reading": self.reading,
            "warnings": self.warnings,
        }


def _reading_broad(f: Fallen, profile: Profile) -> tuple[str, List[str]]:
    """Lectura de un fondo amplio caído. Sin promesas."""
    lectura = (
        f"Un fondo amplio cotiza un {abs(f.drawdown.value):.1f} % por debajo de su máximo "
        "del último año. Es el mismo conjunto de empresas de siempre, a un precio más bajo. "
        "Eso NO significa que vaya a recuperarse, ni cuándo: significa que hoy compras las "
        "mismas participaciones con menos dinero."
    )
    avisos = [
        "Puede seguir bajando. Nadie sabe dónde está el suelo, y quien diga que lo sabe "
        "tampoco.",
    ]
    if profile.monthly_contribution > 0:
        avisos.append(
            f"Tu aporte mensual de US$ {profile.monthly_contribution:,.0f} ya compra más "
            "participaciones cuando el precio está bajo, sin que tengas que acertar el "
            "momento. Esto no te pide adelantarlo ni aumentarlo."
        )
    return lectura, avisos


def _reading_single(f: Fallen) -> tuple[str, List[str]]:
    """Lectura de una acción suelta caída. Aquí el aviso es el contenido."""
    profunda = f.drawdown.value <= DEEP_PCT
    lectura = (
        f"{f.ticker} cotiza un {abs(f.drawdown.value):.1f} % por debajo de su máximo del "
        "último año. En una empresa concreta, esta herramienta NO puede distinguir una "
        "caída pasajera de un negocio deteriorándose: desde fuera se ven igual."
    )
    avisos = [
        "Un precio más bajo que antes no significa barato. Puede que el mercado esté "
        "descontando un problema real que tú todavía no ves.",
    ]
    if profunda:
        avisos.append(
            f"La caída supera el {abs(DEEP_PCT):.0f} %. En ese tramo, históricamente, es más "
            "frecuente que refleje un deterioro de fondo que una rebaja temporal. El motor "
            "de recomendación la penaliza, no la premia."
        )
    if f.held:
        avisos.append(
            "Ya la tienes. La pregunta útil no es si está barata, sino si sigue siendo "
            "cierto lo que escribiste como tu tesis al comprarla."
        )
    else:
        avisos.append(
            "Tu estrategia limita cada acción suelta a un porcentaje pequeño de la cartera. "
            "Que algo haya caído no amplía ese tope."
        )
    return lectura, avisos


def find(
    conn,
    profile: Profile,
    strategy: Strategy,
    state: PortfolioState,
    today: Optional[date] = None,
    with_news: bool = True,
) -> dict:
    """Lo que está por debajo de su máximo, separado por tipo de activo."""
    today = today or date.today()
    held = {p.ticker for p in state.positions}

    caidos: List[Fallen] = []
    problems: List[str] = []

    for ticker in candidate_tickers(conn, state, profile, strategy)[:MAX_TICKERS]:
        try:
            series = prices.fetch_daily(ticker)
        except FetchError as exc:
            problems.append(f"{ticker}: no se pudo obtener el precio ({exc}).")
            continue

        dd = ind.drawdown_from_high(series)
        if not isinstance(dd, DataPoint):
            problems.append(
                f"{ticker}: sin máximo de 52 semanas fiable, así que no se puede medir "
                "la caída. No se muestra en lugar de estimarla."
            )
            continue
        if dd.value > THRESHOLD_PCT:
            continue

        info = lookup_etf(ticker)
        f = Fallen(
            ticker=ticker,
            # Vacio, no el ticker: repetirlo daba "AAPL AAPL" en pantalla. Del
            # catalogo solo salen nombres de ETFs; de una accion suelta no
            # tenemos nombre y decirlo asi es mejor que fingir uno.
            name=info.name if info else "",
            is_broad=is_broad_etf(ticker),
            asset_type="etf" if info else "accion",
            held=ticker in held,
            drawdown=dd,
            last_close=DataPoint(
                label="Último cierre",
                value=series.last.close,
                unit="USD",
                as_of=series.last.day,
                source=series.source,
                precision=2,
            ),
            high_52w=ind.high_52w(series),
        )

        if f.is_broad:
            f.reading, f.warnings = _reading_broad(f, profile)
        else:
            f.reading, f.warnings = _reading_single(f)

        if with_news:
            try:
                f.news = [
                    n.to_dict()
                    for n in news_rss.fetch_news(ticker, None, limit=NEWS_PER_TICKER)
                ]
            except Exception:
                # Sin noticias la pantalla sigue siendo útil: el hecho es la caída.
                f.news = []

        caidos.append(f)

    # Más caído primero dentro de cada grupo. Ordenar es describir, no puntuar:
    # el primero de la lista no es «el mejor», es el que más ha bajado.
    caidos.sort(key=lambda f: f.drawdown.value)
    amplios = [f for f in caidos if f.is_broad]
    sueltas = [f for f in caidos if not f.is_broad]

    return {
        "as_of": today.isoformat(),
        "threshold_pct": THRESHOLD_PCT,
        "broad": [f.to_dict(today) for f in amplios],
        "individual": [f.to_dict(today) for f in sueltas],
        "problems": problems,
        "scope_notice": (
            "Sólo se mira lo que ya está en tu universo: tu watchlist, el núcleo "
            "diversificado y lo que ya tienes. No es un escáner de todo el mercado, y es "
            "a propósito: una lista de lo que más ha caído hoy es una lista de cosas que "
            "pueden seguir cayendo."
        ),
        "order_notice": (
            "Ordenado por cuánto ha caído, no por cuál conviene más. El primero de la "
            "lista es el que más ha bajado, nada más."
        ),
        "no_forecast_notice": (
            "Aquí no hay ninguna previsión de recuperación, ni objetivo de precio, ni "
            "«suele rebotar». Nadie sabe si algo que bajó volverá a subir, ni cuándo. "
            "El único hecho de esta pantalla es cuánto ha caído cada cosa respecto de su "
            "máximo del último año."
        ),
        "news_notice": (
            "Los titulares explican qué se DICE sobre la caída. Son interpretación de "
            "terceros y llegan después de que el precio ya se movió, así que sirven para "
            "entender el contexto, no para decidir con ellos."
        ),
        "empty_notice": (
            f"Nada de tu universo está más de un {abs(THRESHOLD_PCT):.0f} % por debajo de "
            "su máximo del último año. No es una mala noticia ni una buena: es el estado "
            "más habitual."
        ),
    }
