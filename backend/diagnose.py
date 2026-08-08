#!/usr/bin/env python3
"""
Diagnóstico de fuentes de datos: comprueba contra la REALIDAD.

Los tests del repositorio prueban los parsers contra payloads de forma conocida,
pero no pueden demostrar que las fuentes sigan sirviendo eso hoy ni que tu red
las alcance. Este script sí: golpea cada fuente de verdad desde tu máquina y te
dice, una por una, qué funcionó, qué devolvió y qué falló.

Úsalo la primera vez que arranques la herramienta, y cada vez que algo parezca
raro (precios que no cambian, fundamentales ausentes, ninguna noticia).

    .venv/bin/python backend/diagnose.py
    .venv/bin/python backend/diagnose.py --ticker MSFT --etf VTI

Salida: un informe legible y código de salida 0 si todas las fuentes
OBLIGATORIAS responden, 1 si alguna falla. Finnhub y el rastreador STOCK Act son
opcionales: si no están, se avisa pero no se considera fallo.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import CONTACT_EMAIL, FINNHUB_ENABLED, USER_AGENT  # noqa: E402
from app.providers import edgar, finnhub, news_rss, stockact, stooq  # noqa: E402
from app.providers.http import FetchError  # noqa: E402

OK = "  OK "
FAIL = " FALLO"
SKIP = " OMIT"
WARN = " AVISO"


class Report:
    def __init__(self) -> None:
        self.required_failures = 0
        self.warnings = 0

    def line(self, status: str, title: str, detail: str = "") -> None:
        print(f"[{status}] {title}")
        for chunk in (detail or "").splitlines():
            if chunk.strip():
                print(f"         {chunk}")

    def ok(self, title: str, detail: str = "") -> None:
        self.line(OK, title, detail)

    def fail(self, title: str, detail: str = "", required: bool = True) -> None:
        self.line(FAIL, title, detail)
        if required:
            self.required_failures += 1
        else:
            self.warnings += 1

    def warn(self, title: str, detail: str = "") -> None:
        self.line(WARN, title, detail)
        self.warnings += 1

    def skip(self, title: str, detail: str = "") -> None:
        self.line(SKIP, title, detail)


def header(text: str) -> None:
    print()
    print(text)
    print("-" * len(text))


def check_stooq(rep: Report, ticker: str) -> None:
    header(f"Stooq — precios de cierre diario ({ticker})")
    started = time.monotonic()
    try:
        series = stooq.fetch_daily(ticker)
    except FetchError as exc:
        rep.fail(
            "No se pudo obtener la serie de precios.",
            f"{exc}\nSin esta fuente NO hay análisis posible: es la única obligatoria.",
        )
        return
    except Exception:
        rep.fail("Error inesperado parseando Stooq.", traceback.format_exc(limit=3))
        return

    elapsed = time.monotonic() - started
    last = series.last
    age = (__import__("datetime").date.today() - last.day).days
    rep.ok(
        f"{len(series.bars)} cierres, último el {last.day} a {last.close} USD ({elapsed:.1f}s)",
        f"Fuente citada: {series.source.name} — {series.source.url}",
    )
    if len(series.bars) < 250:
        rep.warn(
            "La serie es corta (menos de un año).",
            "Las medias de 200 días y la volatilidad perderán significado.",
        )
    if age > 7:
        rep.warn(
            f"El último cierre tiene {age} días.",
            "Puede ser un símbolo poco líquido o una fuente desactualizada. "
            "La herramienta lo mostrará como dato viejo y bajará la confianza.",
        )


def check_edgar(rep: Report, ticker: str) -> None:
    header(f"SEC EDGAR — fundamentales oficiales ({ticker})")
    if CONTACT_EMAIL.endswith("example.com"):
        rep.warn(
            "No has puesto tu email de contacto.",
            "La SEC exige un User-Agent identificable y puede bloquearte. "
            'Arréglalo con: export INVEST_CONTACT="tu-email@ejemplo.com"',
        )
    print(f"         User-Agent actual: {USER_AGENT}")

    try:
        info = edgar.lookup_cik(ticker)
    except edgar.TickerMapUnavailable as exc:
        rep.fail("No se pudo leer el índice de emisores de la SEC.", str(exc))
        return
    except Exception:
        rep.fail("Error inesperado consultando el índice de la SEC.", traceback.format_exc(limit=3))
        return

    if not info:
        rep.warn(
            f"{ticker} no aparece en el índice de emisores.",
            "Es normal si es un ETF, un ADR o un símbolo no estadounidense.",
        )
        return
    rep.ok(f"CIK resuelto: {info['cik']} — {info['title']}")

    try:
        fundamentals = edgar.fetch_fundamentals(ticker)
    except Exception:
        rep.fail("Error inesperado leyendo companyfacts.", traceback.format_exc(limit=3))
        return

    if fundamentals.unavailable_reason:
        rep.fail("No hay fundamentales.", fundamentals.unavailable_reason)
        return

    lines = []
    for key, fact in sorted(fundamentals.latest.items()):
        lines.append(
            f"{key:<16} {fact.value:>20,.0f} {fact.unit:<10} "
            f"FY{fact.fiscal_year} cierre {fact.period_end} ({fact.form})"
        )
    rep.ok(f"{len(fundamentals.latest)} conceptos leídos:", "\n".join(lines))

    if "revenue" not in fundamentals.latest:
        rep.warn(
            "No se encontraron ingresos anuales.",
            "La empresa puede usar una etiqueta XBRL que la herramienta no conoce.",
        )
    if not fundamentals.previous:
        rep.warn(
            "Sólo hay un ejercicio anual.",
            "Sin el año anterior no se puede calcular el crecimiento de ingresos.",
        )


def check_etf(rep: Report, etf: str) -> None:
    header(f"SEC EDGAR frente a un ETF ({etf})")
    fundamentals = edgar.fetch_fundamentals(etf, "etf")
    if fundamentals.unavailable_reason and "No aplica" in fundamentals.unavailable_reason:
        rep.ok(
            "Se declara correctamente que no aplica.",
            "Un ETF no reporta fundamentales propios, y la herramienta lo dice en vez "
            "de fabricar cifras.",
        )
    else:
        rep.fail(
            "Un ETF debería devolver «no aplica» explícitamente.",
            f"Devolvió: {fundamentals.unavailable_reason or '(nada)'}",
        )


def check_news(rep: Report, ticker: str) -> None:
    header(f"Noticias — RSS de Yahoo Finance y SEC EDGAR ({ticker})")
    try:
        cik_info = edgar.lookup_cik(ticker)
        cik = cik_info["cik"] if cik_info else None
    except Exception:
        cik = None

    yahoo = news_rss.fetch_yahoo(ticker, limit=5)
    if yahoo:
        rep.ok(
            f"{len(yahoo)} titulares de Yahoo Finance.",
            "\n".join(f"{i.published} · {i.title[:70]}" for i in yahoo[:3]),
        )
    else:
        rep.fail(
            "El RSS de Yahoo no devolvió titulares.",
            "Puede ser cobertura nula para este símbolo, o que el feed haya cambiado. "
            "La herramienta seguirá funcionando sin noticias, diciéndolo.",
            required=False,
        )

    filings = news_rss.fetch_sec_filings(cik, limit=5)
    if filings:
        rep.ok(
            f"{len(filings)} presentaciones oficiales en EDGAR.",
            "\n".join(f"{i.published} · {i.title[:70]}" for i in filings[:3]),
        )
    elif cik:
        rep.fail("El feed Atom de EDGAR no devolvió presentaciones.", required=False)
    else:
        rep.skip("Sin CIK, no se consultan presentaciones de la SEC.")


def check_finnhub(rep: Report, ticker: str) -> None:
    header(f"Finnhub — fuente opcional con clave ({ticker})")
    if not FINNHUB_ENABLED:
        rep.skip(
            "No configurada.",
            "La herramienta funciona sin ella con cierres diarios y datos de la SEC. "
            'Para activarla: export FINNHUB_API_KEY="tu_clave" (plan gratuito en finnhub.io).',
        )
        return

    quote = finnhub.fetch_quote(ticker)
    if quote:
        rep.ok(f"Cotización: {quote.formatted()} (dato al {quote.as_of})")
    else:
        rep.fail(
            "No devolvió cotización.",
            "Clave inválida o cuota agotada. La herramienta cae a los cierres de Stooq "
            "en vez de inventar el precio.",
            required=False,
        )

    metrics = finnhub.fetch_metrics(ticker)
    if metrics:
        rep.ok(
            f"{len(metrics)} métricas leídas:",
            "\n".join(f"{m.label}: {m.formatted()}" for m in list(metrics.values())[:6]),
        )
    else:
        rep.fail("No devolvió métricas.", required=False)


def check_stockact(rep: Report) -> None:
    header("Rastreador STOCK Act local — contexto con peso cero")
    if not stockact.available():
        rep.skip(
            "Sin base de datos todavía.",
            "Se genera con «python main.py --ingest-file samples/sample_FD.xml». "
            "Es opcional: sólo añade contexto, nunca influye en una recomendación.",
        )
        return
    top = stockact.top_recent(limit=5)
    rep.ok(
        f"Base disponible, {len(top)} tickers con actividad reciente.",
        "\n".join(f"{t['ticker']}: {t['disclosures']} divulgaciones" for t in top),
    )
    print(f"         {stockact.DISCLOSURE_LAG_NOTICE}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba que las fuentes de datos responden de verdad desde tu máquina."
    )
    parser.add_argument("--ticker", default="AAPL", help="Acción a usar en las pruebas (def: AAPL)")
    parser.add_argument("--etf", default="VOO", help="ETF a usar en las pruebas (def: VOO)")
    parser.add_argument("--skip-news", action="store_true", help="No comprobar los feeds de noticias")
    args = parser.parse_args()

    print("=" * 72)
    print("DIAGNÓSTICO DE FUENTES DE DATOS")
    print("=" * 72)
    print("Esto golpea las fuentes reales. Puede tardar unos segundos: el cliente")
    print("es deliberadamente lento y cortés para no abusar de servicios gratuitos.")

    rep = Report()
    check_stooq(rep, args.etf)
    check_stooq(rep, args.ticker)
    check_edgar(rep, args.ticker)
    check_etf(rep, args.etf)
    if not args.skip_news:
        check_news(rep, args.ticker)
    check_finnhub(rep, args.ticker)
    check_stockact(rep)

    header("RESUMEN")
    if rep.required_failures:
        print(f"{rep.required_failures} fuente(s) obligatoria(s) fallaron.")
        print("La herramienta no podrá analizar hasta que se resuelva. Revisa arriba el")
        print("detalle: casi siempre es red, proxy o un símbolo mal escrito.")
    else:
        print("Todas las fuentes obligatorias responden.")
    if rep.warnings:
        print(f"{rep.warnings} aviso(s): la herramienta funciona, pero con menos datos.")
    print()
    print("Recuerda: esta herramienta es de SOLO LECTURA. No envía órdenes ni se")
    print("conecta a ningún bróker. No es asesoría financiera ni tributaria.")
    return 1 if rep.required_failures else 0


if __name__ == "__main__":
    sys.exit(main())
