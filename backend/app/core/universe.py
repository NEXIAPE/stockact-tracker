"""
Catálogo de referencia de ETFs amplios y clasificación de activos.

POR QUÉ AQUÍ NO HAY NI UN SOLO NÚMERO
-------------------------------------
La tentación sería escribir a mano el ratio de gastos de cada ETF ("VOO cobra
0,03 %"). Eso violaría la regla dura: sería una cifra sin fuente verificable ni
fecha, escrita de memoria por quien programó esto. Los ratios de gastos cambian
y una cifra desactualizada en una herramienta de inversión es peor que ninguna.

Así que el catálogo guarda sólo hechos CUALITATIVOS y estables (quién emite el
ETF, qué tipo de exposición da, si es amplio o temático) más el enlace a la
ficha oficial del emisor. El ratio de gastos aparece como dato FALTANTE hasta
que tú lo leas en esa ficha y lo registres con su fecha
(``POST /api/watchlist/{ticker}/expense-ratio``). Entonces pasa a ser un dato
citado con fuente "Ficha oficial del emisor" y la fecha en que lo leíste.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class EtfInfo:
    ticker: str
    name: str
    issuer: str
    exposure: str          # descripción en lenguaje simple
    breadth: str           # "amplio" | "sectorial" | "tematico" | "bonos"
    asset_class: str       # "acciones" | "bonos" | "mixto"
    factsheet_url: str


def _etf(ticker, name, issuer, exposure, breadth, asset_class, url) -> EtfInfo:
    return EtfInfo(ticker, name, issuer, exposure, breadth, asset_class, url)


# ETFs de referencia habituales para una cartera sencilla y diversificada.
# La lista es un punto de partida para investigar, NO una recomendación.
ETF_CATALOG: Dict[str, EtfInfo] = {
    e.ticker: e
    for e in [
        _etf("VT", "Vanguard Total World Stock ETF", "Vanguard",
             "Acciones de todo el mundo, desarrollados y emergentes, en un solo fondo.",
             "amplio", "acciones", "https://investor.vanguard.com/investment-products/etfs/profile/vt"),
        _etf("VTI", "Vanguard Total Stock Market ETF", "Vanguard",
             "Prácticamente todo el mercado de acciones de EE. UU., grandes y pequeñas.",
             "amplio", "acciones", "https://investor.vanguard.com/investment-products/etfs/profile/vti"),
        _etf("VOO", "Vanguard S&P 500 ETF", "Vanguard",
             "Las 500 mayores empresas cotizadas de EE. UU.",
             "amplio", "acciones", "https://investor.vanguard.com/investment-products/etfs/profile/voo"),
        _etf("IVV", "iShares Core S&P 500 ETF", "BlackRock (iShares)",
             "Las 500 mayores empresas cotizadas de EE. UU.",
             "amplio", "acciones", "https://www.ishares.com/us/products/239726/"),
        _etf("SPY", "SPDR S&P 500 ETF Trust", "State Street (SPDR)",
             "Las 500 mayores empresas cotizadas de EE. UU. El ETF más antiguo y negociado.",
             "amplio", "acciones", "https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy"),
        _etf("ITOT", "iShares Core S&P Total U.S. Stock Market ETF", "BlackRock (iShares)",
             "Todo el mercado accionario estadounidense.",
             "amplio", "acciones", "https://www.ishares.com/us/products/239724/"),
        _etf("VXUS", "Vanguard Total International Stock ETF", "Vanguard",
             "Acciones de fuera de EE. UU.: Europa, Asia y emergentes.",
             "amplio", "acciones", "https://investor.vanguard.com/investment-products/etfs/profile/vxus"),
        _etf("VEA", "Vanguard FTSE Developed Markets ETF", "Vanguard",
             "Acciones de países desarrollados fuera de EE. UU.",
             "amplio", "acciones", "https://investor.vanguard.com/investment-products/etfs/profile/vea"),
        _etf("VWO", "Vanguard FTSE Emerging Markets ETF", "Vanguard",
             "Acciones de países emergentes.",
             "amplio", "acciones", "https://investor.vanguard.com/investment-products/etfs/profile/vwo"),
        _etf("BND", "Vanguard Total Bond Market ETF", "Vanguard",
             "Bonos estadounidenses de grado de inversión. Suele amortiguar las caídas de las acciones.",
             "bonos", "bonos", "https://investor.vanguard.com/investment-products/etfs/profile/bnd"),
        _etf("AGG", "iShares Core U.S. Aggregate Bond ETF", "BlackRock (iShares)",
             "Bonos estadounidenses de grado de inversión.",
             "bonos", "bonos", "https://www.ishares.com/us/products/239458/"),
        _etf("BNDW", "Vanguard Total World Bond ETF", "Vanguard",
             "Bonos de todo el mundo.",
             "bonos", "bonos", "https://investor.vanguard.com/investment-products/etfs/profile/bndw"),
        _etf("SCHD", "Schwab U.S. Dividend Equity ETF", "Charles Schwab",
             "Empresas estadounidenses con historial de dividendos. Más concentrado que un índice total.",
             "sectorial", "acciones", "https://www.schwabassetmanagement.com/products/schd"),
        _etf("QQQ", "Invesco QQQ Trust", "Invesco",
             "Las mayores empresas no financieras del Nasdaq. MUY cargado a tecnología: no es un índice amplio.",
             "sectorial", "acciones", "https://www.invesco.com/qqq-etf/en/home.html"),
    ]
}

# ETFs considerados "amplios y diversificados" a efectos de la protección de
# principiante. Un ETF sectorial o temático NO cuenta como diversificación.
BROAD_ETFS = {t for t, e in ETF_CATALOG.items() if e.breadth in ("amplio", "bonos")}

# Punto de partida para las ideas proactivas de un perfil principiante.
BEGINNER_STARTING_UNIVERSE = ["VT", "VTI", "VOO", "VXUS", "BND", "AGG"]


def lookup_etf(ticker: str) -> Optional[EtfInfo]:
    return ETF_CATALOG.get(ticker.strip().upper())


def is_broad_etf(ticker: str) -> bool:
    return ticker.strip().upper() in BROAD_ETFS


def guess_asset_type(ticker: str, declared: Optional[str] = None) -> str:
    """Tipo de activo. Lo declarado por ti manda; si no, se mira el catálogo."""
    if declared in ("accion", "etf"):
        return declared
    return "etf" if lookup_etf(ticker) else "accion"


def etf_dict(info: EtfInfo) -> dict:
    return {
        "ticker": info.ticker,
        "name": info.name,
        "issuer": info.issuer,
        "exposure": info.exposure,
        "breadth": info.breadth,
        "asset_class": info.asset_class,
        "factsheet_url": info.factsheet_url,
        "is_broad": info.ticker in BROAD_ETFS,
    }


def catalog() -> List[dict]:
    return [etf_dict(e) for e in ETF_CATALOG.values()]
