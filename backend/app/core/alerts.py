"""
Alertas: "vale la pena mirar", nunca "actúa ya".

Toda alerta pasa por el guardián anti-FOMO antes de guardarse. Si un texto
suena a urgencia o a miedo a quedarse fuera, la generación falla en vez de
mostrarlo. El objetivo explícito de este módulo es que NO operes de más.

Cuatro tipos, tal como pediste:
  1. noticia   — algo relevante publicado sobre un activo que tienes.
  2. precio    — un movimiento fuerte en un activo que tienes o sigues.
  3. criterio  — un ticker de tu watchlist cumple un criterio que TÚ fijaste.
  4. cartera   — tu cartera se ha desviado de tu propia estrategia.

Cada alerta se guarda con una huella (``fingerprint``) para que la misma cosa
no te avise dos veces.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from ..db import dumps, now_iso
from ..providers import news_rss, stooq
from ..providers.http import FetchError
from . import indicators as ind
from .datapoint import DataPoint, Datum, user_source
from .guards import assert_no_pressure_language
from .portfolio import PortfolioState, check_deviations
from .profile import Profile, Strategy

# Umbral de "movimiento fuerte" en una sola sesión. Deliberadamente alto: un
# 2 % diario es ruido normal y avisarte de ello sólo generaría ansiedad.
STRONG_MOVE_PCT = 5.0

FRAMING = (
    "Esto es algo que vale la pena mirar cuando tengas un rato. No hay nada que "
    "hacer hoy, y reaccionar rápido a una alerta suele salir peor que no hacer nada."
)


@dataclass
class Alert:
    kind: str
    ticker: str
    title: str
    body: str
    evidence: List[Datum] = field(default_factory=list)
    day: date = field(default_factory=date.today)

    def fingerprint(self) -> str:
        raw = f"{self.kind}|{self.ticker}|{self.title}|{self.day.isoformat()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "ticker": self.ticker,
            "title": self.title,
            "body": self.body,
            "evidence": [d.to_dict(self.day) for d in self.evidence],
        }


def _check(alert: Alert) -> Alert:
    assert_no_pressure_language(alert.title, f"título de alerta ({alert.kind})")
    assert_no_pressure_language(alert.body, f"cuerpo de alerta ({alert.kind})")
    return alert


# ---------------------------------------------------------------------------
# Generadores
# ---------------------------------------------------------------------------
def _price_alerts(tickers: List[str], today: date) -> tuple[List[Alert], List[str]]:
    out: List[Alert] = []
    problems: List[str] = []
    for ticker in tickers:
        try:
            series = stooq.fetch_daily(ticker)
        except FetchError as exc:
            problems.append(f"{ticker}: sin precio ({exc}).")
            continue

        change = ind.daily_change(series)
        if not isinstance(change, DataPoint):
            continue
        if abs(change.value) < STRONG_MOVE_PCT:
            continue

        direction = "subido" if change.value > 0 else "bajado"
        out.append(
            _check(
                Alert(
                    kind="precio",
                    ticker=ticker,
                    title=f"{ticker} ha {direction} con fuerza en la última sesión",
                    body=(
                        f"El cierre de {ticker} se movió bastante más de lo habitual en una sola "
                        f"sesión. Un movimiento grande en un día no dice, por sí solo, si algo "
                        f"cambió de verdad en el activo. {FRAMING}"
                    ),
                    evidence=[change, ind.last_close(series)],
                    day=series.last.day,
                )
            )
        )
    return out, problems


def _news_alerts(conn, tickers: List[str], today: date) -> List[Alert]:
    out: List[Alert] = []
    recent_cutoff = today - timedelta(days=2)
    for ticker in tickers:
        items = news_rss.fetch_news(ticker, limit=5)
        fresh = [
            i for i in items
            if i.published and i.published >= recent_cutoff and i.kind == "presentacion_oficial"
        ]
        # Se priorizan las presentaciones oficiales (hechos comunicados a la SEC)
        # sobre los titulares de prensa, que son opinión.
        if not fresh:
            fresh = [i for i in items if i.published and i.published >= recent_cutoff][:1]
        for item in fresh[:1]:
            out.append(
                _check(
                    Alert(
                        kind="noticia",
                        ticker=ticker,
                        title=f"Hay novedades publicadas sobre {ticker}",
                        body=(
                            f"«{item.title}» — {item.source_name}, "
                            f"{item.published.isoformat() if item.published else 'sin fecha'}. "
                            f"{item.to_dict()['interpretation_notice']} {FRAMING}"
                        ),
                        day=item.published or today,
                    )
                )
            )
    return out


def _criteria_alerts(conn, today: date) -> tuple[List[Alert], List[str]]:
    out: List[Alert] = []
    problems: List[str] = []
    rows = conn.execute("SELECT * FROM watchlist").fetchall()
    src = user_source()

    for row in rows:
        ticker = row["ticker"].upper()
        target = row["target_buy_price"]
        max_dd = row["max_drawdown_pct"]
        if target is None and max_dd is None:
            continue
        try:
            series = stooq.fetch_daily(ticker)
        except FetchError as exc:
            problems.append(f"{ticker}: sin precio ({exc}).")
            continue

        close = ind.last_close(series)

        if target is not None and close.value <= float(target):
            out.append(
                _check(
                    Alert(
                        kind="criterio",
                        ticker=ticker,
                        title=f"{ticker} está por debajo del precio que tú fijaste",
                        body=(
                            f"Pusiste un precio de referencia para volver a mirar {ticker} y el "
                            f"último cierre está en ese nivel o por debajo. Que haya llegado a tu "
                            f"precio no significa que sea buena compra: el precio pudo bajar por "
                            f"una razón. Analízalo antes de decidir. {FRAMING}"
                        ),
                        evidence=[
                            close,
                            DataPoint(
                                label=f"Precio de referencia que fijaste para {ticker}",
                                value=float(target),
                                unit="USD",
                                as_of=today,
                                source=src,
                            ),
                        ],
                        day=series.last.day,
                    )
                )
            )

        if max_dd is not None:
            dd = ind.drawdown_from_high(series)
            if isinstance(dd, DataPoint) and dd.value <= -abs(float(max_dd)):
                out.append(
                    _check(
                        Alert(
                            kind="criterio",
                            ticker=ticker,
                            title=f"{ticker} ha caído desde máximos más de lo que marcaste",
                            body=(
                                f"Fijaste un umbral de caída desde el máximo de 52 semanas para "
                                f"{ticker} y el precio lo ha superado. Una caída grande puede ser "
                                f"una oportunidad o una señal de deterioro; los datos por sí solos "
                                f"no distinguen entre las dos cosas. {FRAMING}"
                            ),
                            evidence=[
                                dd,
                                DataPoint(
                                    label=f"Umbral de caída que fijaste para {ticker}",
                                    value=-abs(float(max_dd)),
                                    unit="%",
                                    as_of=today,
                                    source=src,
                                    precision=1,
                                ),
                            ],
                            day=series.last.day,
                        )
                    )
                )
    return out, problems


def _portfolio_alerts(
    state: PortfolioState, profile: Profile, strategy: Strategy, today: date
) -> List[Alert]:
    out: List[Alert] = []
    for dev in check_deviations(state, profile, strategy):
        if dev.severity != "atencion":
            continue
        out.append(
            _check(
                Alert(
                    kind="cartera",
                    ticker="",
                    title="Tu cartera se ha alejado de tu propia estrategia",
                    body=f"{dev.message} {FRAMING}",
                    evidence=list(dev.numbers),
                    day=today,
                )
            )
        )
    return out


# ---------------------------------------------------------------------------
# Orquestación y persistencia
# ---------------------------------------------------------------------------
def generate_and_store(
    conn,
    profile: Profile,
    strategy: Strategy,
    state: PortfolioState,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()

    held = [p.ticker for p in state.positions]
    watched = [r["ticker"].upper() for r in conn.execute("SELECT ticker FROM watchlist").fetchall()]
    followed = list(dict.fromkeys(held + watched))

    alerts: List[Alert] = []
    problems: List[str] = []

    price_alerts, price_problems = _price_alerts(followed, today)
    alerts += price_alerts
    problems += price_problems

    alerts += _news_alerts(conn, held, today)

    criteria_alerts, criteria_problems = _criteria_alerts(conn, today)
    alerts += criteria_alerts
    problems += criteria_problems

    alerts += _portfolio_alerts(state, profile, strategy, today)

    stored = 0
    for alert in alerts:
        fp = alert.fingerprint()
        exists = conn.execute("SELECT 1 FROM alerts WHERE fingerprint = ?", (fp,)).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO alerts (fingerprint, kind, ticker, title, body, evidence, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                fp,
                alert.kind,
                alert.ticker,
                alert.title,
                alert.body,
                dumps([d.to_dict(today) for d in alert.evidence]),
                now_iso(),
            ),
        )
        stored += 1

    conn.execute("INSERT INTO runs (kind, ran_at) VALUES (?,?)", ("alerts", now_iso()))

    return {
        "generated": len(alerts),
        "new": stored,
        "problems": problems,
        "checked_tickers": followed,
    }


def list_alerts(conn, only_unread: bool = False, limit: int = 50) -> List[dict]:
    from ..db import loads

    sql = "SELECT * FROM alerts"
    if only_unread:
        sql += " WHERE read_at IS NULL"
    sql += " ORDER BY created_at DESC LIMIT ?"
    rows = conn.execute(sql, (limit,)).fetchall()
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "ticker": r["ticker"],
            "title": r["title"],
            "body": r["body"],
            "evidence": loads(r["evidence"], []),
            "created_at": r["created_at"],
            "read": r["read_at"] is not None,
        }
        for r in rows
    ]
