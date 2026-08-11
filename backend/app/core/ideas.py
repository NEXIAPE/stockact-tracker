"""
Ideas proactivas: candidatos que encajan con tu perfil.

Son PUNTOS DE PARTIDA PARA INVESTIGAR, no órdenes. Cada idea pasa por el mismo
motor de recomendación que el análisis bajo demanda, así que llega con sus
riesgos, su contra-argumento y su nivel de confianza. Una idea sin contra-caso
no se muestra: la regla dura aplica también aquí.

De dónde salen los candidatos:
  * Un universo de partida de ETFs amplios, sesgado a diversificación porque
    es lo que corresponde a un perfil principiante.
  * Tu watchlist: lo que tú decidiste seguir.
  * Lo que ya tienes: para detectar si algo dejó de encajar.

Deliberadamente NO hay un buscador de "acciones de moda". Proponer lo que más
sube es la forma más rápida de que compres caro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from .portfolio import PortfolioState
from .profile import Profile, Strategy
from . import thesis as thesis_mod
from .recommendation import InsufficientData, Recommendation, analyze
from .universe import BEGINNER_STARTING_UNIVERSE, lookup_etf

MAX_CANDIDATES = 8


def candidate_tickers(
    conn, state: PortfolioState, profile: Profile, strategy: Strategy
) -> List[str]:
    """Universo a evaluar, sin duplicados y con un tope para no abusar de las fuentes."""
    seen: List[str] = []

    def add(t: str) -> None:
        t = (t or "").strip().upper()
        if t and t not in seen:
            seen.append(t)

    # 1. Tu watchlist manda: es lo que tú dijiste que te interesa.
    for row in conn.execute("SELECT ticker FROM watchlist ORDER BY created_at DESC").fetchall():
        add(row["ticker"])

    # 2. Núcleo diversificado que aún no tienes.
    held = {p.ticker for p in state.positions}
    mix = state.stocks_vs_bonds()
    needs_bonds = (
        mix["bonos"] is not None and mix["bonos"] < strategy.target_bonds_pct - 5
    )
    for t in BEGINNER_STARTING_UNIVERSE:
        info = lookup_etf(t)
        if t in held:
            continue
        if info and info.asset_class == "bonos" and not needs_bonds:
            continue
        add(t)

    # 3. Lo que ya tienes, para revisar si sigue encajando.
    for t in sorted(held):
        add(t)

    return seen[:MAX_CANDIDATES]


# Aviso imprescindible al mostrar VARIAS ideas juntas: cada importe sugerido se
# calcula suponiendo que esa idea es la única. Vistas en lista, sin este aviso,
# tres ideas de mil dólares parecen tres mil dólares a gastar.
ALTERNATIVES_NOTICE = (
    "Los importes sugeridos son ALTERNATIVAS entre sí, no se suman. Cada uno se calcula "
    "como si esa fuera la única idea que sigues, usando el mismo efectivo. Si te interesan "
    "varias, el dinero disponible hay que repartirlo, no multiplicarlo."
)


@dataclass
class Idea:
    recommendation: Recommendation
    why_surfaced: str

    def to_dict(self) -> dict:
        d = self.recommendation.to_dict()
        d["why_surfaced"] = self.why_surfaced
        d["sizing_is_alternative"] = True
        return d


def _why(ticker: str, state: PortfolioState, strategy: Strategy, in_watchlist: bool) -> str:
    if in_watchlist:
        return "Está en tu watchlist, así que lo reviso por ti."
    info = lookup_etf(ticker)
    if info and info.asset_class == "bonos":
        return (
            "Tu cartera va corta de bonos frente al objetivo que salió de tu perfil, y este "
            "fondo cubre precisamente esa parte."
        )
    if info and info.breadth == "amplio":
        return (
            "Es un fondo amplio que da exposición a muchas empresas de una vez, que es la "
            "base habitual de una cartera para quien empieza."
        )
    if ticker in {p.ticker for p in state.positions}:
        return "Ya lo tienes: lo reviso para ver si sigue encajando con tu plan."
    return "Encaja con el tipo de activo que tu estrategia contempla."


def generate(
    conn,
    profile: Profile,
    strategy: Strategy,
    state: PortfolioState,
    limit: int = 4,
    today: Optional[date] = None,
) -> tuple[List[Idea], List[str]]:
    """Devuelve ideas ordenadas por encaje, y la lista de símbolos que fallaron."""
    watch = {
        r["ticker"].upper()
        for r in conn.execute("SELECT ticker FROM watchlist").fetchall()
    }
    problems: List[str] = []
    scored: List[tuple[float, Idea]] = []

    for ticker in candidate_tickers(conn, state, profile, strategy):
        try:
            rec = analyze(ticker, profile, strategy, state, today=today,
                          position_thesis=thesis_mod.load(conn, ticker))
        except InsufficientData as exc:
            problems.append(f"{ticker}: {exc.detail}")
            continue
        except Exception as exc:  # una fuente caída no debe tumbar el briefing
            problems.append(f"{ticker}: no se pudo analizar ({exc}).")
            continue

        idea = Idea(recommendation=rec, why_surfaced=_why(ticker, state, strategy, ticker in watch))
        # Prioriza ideas accionables, pero conserva las de "revisar" por debajo.
        priority = rec.score + (25.0 if rec.action == "comprar" else 0.0)
        scored.append((priority, idea))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [idea for _, idea in scored[:limit]], problems
