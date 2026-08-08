"""
Fundamentales oficiales desde SEC EDGAR (gratis, sin API key).

La SEC publica los datos XBRL de todos los emisores estadounidenses en
``data.sec.gov``. Es la fuente ORIGINAL: no es una estimación de un tercero,
son las cifras que la empresa reportó en su 10-K/10-Q. Por eso cada número que
sale de aquí se puede citar con su fecha de cierre de periodo y su formulario.

Limitación honesta e importante: **los ETFs no tienen fundamentales aquí.** Un
ETF no reporta ingresos ni márgenes. Cuando pidas un ETF, este proveedor
devuelve "no aplica" explícitamente en vez de fabricar algo.

La SEC exige un User-Agent identificable y limita la tasa de peticiones; el
cliente HTTP cortés se encarga de ambas cosas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

from ..config import CACHE_TTL
from ..core.datapoint import DataPoint, Missing, Source
from .http import FetchError, client

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FILING_HOME = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}&type=10-K"

# Conceptos us-gaap que nos interesan, con alternativas por orden de preferencia
# (las empresas no usan todas la misma etiqueta).
CONCEPTS: Dict[str, List[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "liabilities": ["Liabilities"],
    "assets": ["Assets"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}


@dataclass
class AnnualFact:
    concept: str
    value: float
    unit: str
    period_end: date
    fiscal_year: int
    form: str


@dataclass
class Fundamentals:
    ticker: str
    cik: Optional[int]
    company_name: str
    source: Source
    latest: Dict[str, AnnualFact] = field(default_factory=dict)
    previous: Dict[str, AnnualFact] = field(default_factory=dict)
    unavailable_reason: str = ""

    def datapoint(self, key: str, label: str, unit: str, precision: int = 2) -> DataPoint | Missing:
        fact = self.latest.get(key)
        if fact is None:
            return Missing(
                label=label,
                reason=self.unavailable_reason
                or f"SEC EDGAR no publica '{key}' para {self.ticker} en el último ejercicio anual.",
                tried="SEC EDGAR XBRL companyfacts",
            )
        return DataPoint(
            label=f"{label} (ejercicio {fact.fiscal_year}, {fact.form})",
            value=fact.value,
            unit=unit,
            as_of=fact.period_end,
            source=self.source,
            precision=precision,
        )


def _load_ticker_map() -> Dict[str, dict]:
    raw = client().get(TICKER_MAP_URL, ttl=CACHE_TTL["tickermap"])
    data = json.loads(raw.decode("utf-8", "replace"))
    mapping: Dict[str, dict] = {}
    for entry in data.values():
        ticker = str(entry.get("ticker", "")).upper()
        if ticker:
            mapping[ticker] = {
                "cik": int(entry.get("cik_str", 0)),
                "title": entry.get("title", ""),
            }
    return mapping


class TickerMapUnavailable(RuntimeError):
    """No se pudo leer el índice de emisores de la SEC.

    Existe como excepción propia para poder distinguir dos cosas que NO son lo
    mismo: «este símbolo no está registrado en la SEC» y «no pude preguntárselo
    a la SEC». Confundirlas haría que la herramienta afirmara algo falso sobre
    un dato, que es precisamente lo que tiene prohibido.
    """


def lookup_cik(ticker: str) -> Optional[dict]:
    """CIK del emisor, o ``None`` si el símbolo no está registrado.

    Lanza ``TickerMapUnavailable`` si la fuente no responde.
    """
    try:
        mapping = _load_ticker_map()
    except (FetchError, ValueError) as exc:
        raise TickerMapUnavailable(str(exc)) from exc
    return mapping.get(ticker.strip().upper())


def _pick_annual(units: dict, concept: str) -> List[AnnualFact]:
    """Extrae los hechos ANUALES (10-K, periodo completo) de un concepto."""
    facts: List[AnnualFact] = []
    for unit_name, entries in units.items():
        for e in entries:
            if e.get("fp") != "FY" or e.get("form") not in ("10-K", "20-F", "40-F"):
                continue
            end = e.get("end")
            val = e.get("val")
            fy = e.get("fy")
            if end is None or val is None or fy is None:
                continue
            # Para magnitudes de flujo (ingresos, beneficio) exigimos un periodo
            # de ~1 año, para no mezclar un trimestre etiquetado como FY.
            start = e.get("start")
            if start:
                try:
                    days = (datetime.strptime(end, "%Y-%m-%d").date()
                            - datetime.strptime(start, "%Y-%m-%d").date()).days
                except ValueError:
                    days = 365
                if days < 300:
                    continue
            try:
                facts.append(
                    AnnualFact(
                        concept=concept,
                        value=float(val),
                        unit=unit_name,
                        period_end=datetime.strptime(end, "%Y-%m-%d").date(),
                        fiscal_year=int(fy),
                        form=str(e.get("form")),
                    )
                )
            except (ValueError, TypeError):
                continue
    facts.sort(key=lambda f: f.period_end)
    return facts


def fetch_fundamentals(ticker: str, asset_type: str = "accion") -> Fundamentals:
    """Fundamentales anuales del último ejercicio y del anterior (para YoY)."""
    ticker = ticker.strip().upper()

    if asset_type == "etf":
        return Fundamentals(
            ticker=ticker,
            cik=None,
            company_name="",
            source=Source(name="SEC EDGAR (XBRL)", url="https://data.sec.gov/"),
            unavailable_reason=(
                "No aplica: un ETF es una cesta de activos y no reporta ingresos, "
                "márgenes ni deuda propios. Para un ETF miran otras cosas: qué "
                "índice replica, cuánto cobra de comisión y cuán diversificado está."
            ),
        )

    base_source = Source(name="SEC EDGAR (XBRL)", url="https://data.sec.gov/")

    try:
        info = lookup_cik(ticker)
    except TickerMapUnavailable as exc:
        # No se pudo preguntar. Decirlo así, y NO como «no existe»: son cosas
        # distintas y confundirlas sería afirmar algo falso.
        return Fundamentals(
            ticker=ticker,
            cik=None,
            company_name="",
            source=base_source,
            unavailable_reason=(
                f"No se pudo consultar el índice de emisores de la SEC ahora mismo, así que "
                f"no sé si {ticker} está registrado ni puedo leer sus fundamentales. Esto es "
                f"un fallo de conexión, no una afirmación sobre la empresa. Detalle: {exc}"
            ),
        )

    if not info:
        return Fundamentals(
            ticker=ticker,
            cik=None,
            company_name="",
            source=base_source,
            unavailable_reason=(
                f"{ticker} no aparece en el índice de emisores de la SEC. Puede ser un "
                f"ETF, un ADR o un símbolo no estadounidense."
            ),
        )

    cik = info["cik"]
    source = Source(
        name="SEC EDGAR (XBRL companyfacts)",
        url=FILING_HOME.format(cik=cik),
    )

    try:
        raw = client().get(FACTS_URL.format(cik=cik), ttl=CACHE_TTL["fundamentals"])
        data = json.loads(raw.decode("utf-8", "replace"))
    except (FetchError, ValueError) as exc:
        return Fundamentals(
            ticker=ticker,
            cik=cik,
            company_name=info["title"],
            source=source,
            unavailable_reason=f"No se pudo leer SEC EDGAR ahora mismo: {exc}",
        )

    us_gaap = (data.get("facts") or {}).get("us-gaap") or {}
    result = Fundamentals(
        ticker=ticker, cik=cik, company_name=data.get("entityName", info["title"]), source=source
    )

    for key, candidates in CONCEPTS.items():
        for concept in candidates:
            node = us_gaap.get(concept)
            if not node:
                continue
            facts = _pick_annual(node.get("units") or {}, concept)
            if not facts:
                continue
            result.latest[key] = facts[-1]
            if len(facts) >= 2:
                result.previous[key] = facts[-2]
            break

    if not result.latest:
        result.unavailable_reason = (
            f"SEC EDGAR tiene a {ticker} registrado pero no publicó los conceptos "
            f"financieros estándar que la herramienta sabe leer."
        )
    return result
