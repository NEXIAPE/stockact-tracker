"""
Tests de los PARSERS de cada proveedor, contra payloads con la forma documentada.

Qué demuestran: que el parseo maneja bien la estructura esperada — orden de
columnas, formatos de fecha, unidades, campos ausentes y filas corruptas — y que
ante datos malos NUNCA se inventa un valor.

Qué NO demuestran: que la fuente siga sirviendo hoy exactamente ese formato. Los
fixtures están escritos a mano, no grabados (ver tests/fixtures/README.md). Para
comprobar la realidad está ``backend/diagnose.py``, que golpea las fuentes de
verdad desde tu máquina y te dice qué funcionó.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.core.datapoint import DataPoint
from app.providers import edgar, finnhub, news_rss, prices, stooq, twelvedata, yahoo_chart
from app.providers.http import FetchError

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture()
def serve(monkeypatch):
    """Sustituye la capa HTTP por un servidor de fixtures gobernado por la URL."""

    def make(routes: dict, default=None):
        def fake_get(self, url, *, ttl=0, headers=None, cache_key=None):
            for fragment, payload in routes.items():
                if fragment in url:
                    if isinstance(payload, Exception):
                        raise payload
                    return payload
            if default is not None:
                return default
            raise FetchError(f"Sin fixture para {url}")

        monkeypatch.setattr("app.providers.http.PoliteClient.get", fake_get)

    return make


# ---------------------------------------------------------------------------
class TestStooqParser:
    def test_parses_daily_bars_in_order(self, serve):
        serve({"stooq.com": load("stooq_voo.csv")})
        series = stooq.fetch_daily("VOO")
        assert len(series.bars) == 6
        assert series.bars[0].day == date(2026, 7, 30)
        assert series.last.day == date(2026, 8, 6)
        assert series.last.close == pytest.approx(501.77)
        assert [b.day for b in series.bars] == sorted(b.day for b in series.bars)

    def test_source_is_cited_with_a_url(self, serve):
        serve({"stooq.com": load("stooq_voo.csv")})
        series = stooq.fetch_daily("VOO")
        assert "Stooq" in series.source.name
        assert series.source.url.startswith("https://")

    def test_us_suffix_is_added_to_the_symbol(self, serve):
        captured = {}

        def fake_get(self, url, *, ttl=0, headers=None, cache_key=None):
            captured["url"] = url
            return load("stooq_voo.csv")

        import app.providers.http as http_mod

        original = http_mod.PoliteClient.get
        http_mod.PoliteClient.get = fake_get
        try:
            stooq.fetch_daily("BRK.B")
        finally:
            http_mod.PoliteClient.get = original
        assert "brk-b.us" in captured["url"]

    def test_no_data_response_raises_instead_of_returning_empty(self, serve):
        serve({"stooq.com": load("stooq_nodata.txt")})
        with pytest.raises(FetchError):
            stooq.fetch_daily("ZZZZ")

    def test_corrupt_rows_are_skipped_not_zero_filled(self, serve):
        """Una fila ilegible se descarta. Convertirla en 0.0 sería inventar un precio."""
        serve({"stooq.com": load("stooq_corrupt.csv")})
        series = stooq.fetch_daily("VOO")
        assert len(series.bars) == 2
        assert all(b.close > 0 for b in series.bars)

    def test_network_failure_propagates_as_fetch_error(self, serve):
        serve({"stooq.com": FetchError("caído")})
        with pytest.raises(FetchError):
            stooq.fetch_daily("VOO")


# ---------------------------------------------------------------------------
class TestEdgarParser:
    def _serve_all(self, serve):
        serve({
            "company_tickers.json": load("edgar_tickers.json"),
            "companyfacts": load("edgar_companyfacts.json"),
        })

    def test_resolves_ticker_to_cik(self, serve):
        self._serve_all(serve)
        assert edgar.lookup_cik("AAPL")["cik"] == 320193

    def test_ticker_lookup_is_case_insensitive(self, serve):
        self._serve_all(serve)
        assert edgar.lookup_cik("aapl")["cik"] == 320193

    def test_picks_the_latest_annual_figures(self, serve):
        self._serve_all(serve)
        f = edgar.fetch_fundamentals("AAPL")
        assert f.latest["revenue"].fiscal_year == 2025
        assert f.latest["revenue"].value == pytest.approx(416160000000)
        assert f.previous["revenue"].fiscal_year == 2024

    def test_ignores_quarterly_rows_even_when_labelled_fy(self, serve):
        """El fixture trae un periodo de un trimestre marcado fp=FY form=10-K.
        Tomarlo como anual falsearía el crecimiento de ingresos."""
        self._serve_all(serve)
        f = edgar.fetch_fundamentals("AAPL")
        assert f.latest["revenue"].value != pytest.approx(124300000000)

    def test_ignores_10q_rows(self, serve):
        self._serve_all(serve)
        f = edgar.fetch_fundamentals("AAPL")
        assert all(fact.form == "10-K" for fact in f.latest.values())

    def test_balance_sheet_items_have_no_start_date(self, serve):
        self._serve_all(serve)
        f = edgar.fetch_fundamentals("AAPL")
        assert f.latest["equity"].period_end == date(2025, 9, 27)
        assert f.latest["liabilities"].value == pytest.approx(277300000000)

    def test_datapoints_carry_period_end_as_the_data_date(self, serve):
        self._serve_all(serve)
        f = edgar.fetch_fundamentals("AAPL")
        dp = f.datapoint("net_income", "Beneficio neto anual", "USD")
        assert isinstance(dp, DataPoint)
        assert dp.as_of == date(2025, 9, 27)
        assert "2025" in dp.label
        assert "EDGAR" in dp.source.name

    def test_absent_concept_returns_missing_with_a_reason(self, serve):
        self._serve_all(serve)
        f = edgar.fetch_fundamentals("AAPL")
        missing = f.datapoint("long_term_debt", "Deuda a largo plazo", "USD")
        assert missing.__class__.__name__ == "Missing"
        assert missing.reason

    def test_entity_name_comes_from_the_filing(self, serve):
        self._serve_all(serve)
        assert edgar.fetch_fundamentals("AAPL").company_name == "Apple Inc."


# ---------------------------------------------------------------------------
class TestNewsParsers:
    def test_yahoo_rss_items_are_parsed_with_dates(self, serve):
        serve({"feeds.finance.yahoo.com": load("yahoo_rss.xml")})
        items = news_rss.fetch_yahoo("AAPL")
        assert len(items) == 3  # el que no tiene enlace se descarta
        assert items[0].published == date(2026, 8, 6)
        assert items[1].published == date(2026, 8, 5)
        assert items[2].published is None  # sin fecha: se dice, no se inventa

    def test_html_is_stripped_from_descriptions(self, serve):
        serve({"feeds.finance.yahoo.com": load("yahoo_rss.xml")})
        first = news_rss.fetch_yahoo("AAPL")[0]
        assert "<p>" not in first.summary
        assert "superó las expectativas" in first.summary

    def test_press_items_are_labelled_as_interpretation(self, serve):
        serve({"feeds.finance.yahoo.com": load("yahoo_rss.xml")})
        item = news_rss.fetch_yahoo("AAPL")[0].to_dict()
        assert item["kind"] == "prensa"
        assert "INTERPRETACIÓN" in item["interpretation_notice"]

    def test_sec_filings_are_labelled_as_official_documents(self, serve):
        serve({"browse-edgar": load("edgar_atom.xml")})
        items = news_rss.fetch_sec_filings(320193)
        assert len(items) == 2
        assert items[0].kind == "presentacion_oficial"
        assert items[0].published == date(2026, 8, 7)
        assert "sec.gov" in items[0].url
        assert "oficial" in items[0].to_dict()["interpretation_notice"].lower()

    def test_combined_feed_is_sorted_newest_first(self, serve):
        serve({
            "feeds.finance.yahoo.com": load("yahoo_rss.xml"),
            "browse-edgar": load("edgar_atom.xml"),
        })
        items = news_rss.fetch_news("AAPL", 320193)
        dated = [i.published for i in items if i.published]
        assert dated == sorted(dated, reverse=True)

    def test_a_broken_feed_yields_nothing_rather_than_crashing(self, serve):
        serve({"feeds.finance.yahoo.com": b"<<< no es xml"})
        assert news_rss.fetch_yahoo("AAPL") == []

    def test_no_cik_means_no_sec_call(self, serve):
        serve({})
        assert news_rss.fetch_sec_filings(None) == []


# ---------------------------------------------------------------------------
class TestFinnhubParser:
    @pytest.fixture(autouse=True)
    def _enable(self, monkeypatch):
        monkeypatch.setattr(finnhub, "FINNHUB_ENABLED", True)
        monkeypatch.setattr(finnhub, "FINNHUB_API_KEY", "clave-de-prueba")

    def test_disabled_without_a_key(self, monkeypatch, serve):
        monkeypatch.setattr(finnhub, "FINNHUB_ENABLED", False)
        serve({})
        assert finnhub.enabled() is False
        assert finnhub.fetch_quote("AAPL") is None
        assert finnhub.fetch_metrics("AAPL") == {}

    def test_quote_is_parsed_with_its_timestamp(self, serve):
        # El fixture usa una marca de tiempo de media sesión estadounidense
        # (20:30 UTC = 16:30 en Nueva York) a propósito: a medianoche UTC exacta
        # la fecha sería ambigua y el test no probaría nada útil.
        serve({"/quote": load("finnhub_quote.json")})
        q = finnhub.fetch_quote("AAPL")
        assert isinstance(q, DataPoint)
        assert q.value == pytest.approx(237.15)
        assert q.unit == "USD"
        assert q.as_of == date(2026, 8, 6)

    def test_only_known_metrics_are_read(self, serve):
        serve({"/stock/metric": load("finnhub_metrics.json")})
        metrics = finnhub.fetch_metrics("AAPL")
        assert "peBasicExclExtraTTM" in metrics
        assert "beta" in metrics
        assert "unknownMetricWeDoNotRead" not in metrics

    def test_null_metric_is_skipped_not_zeroed(self, serve):
        serve({"/stock/metric": load("finnhub_metrics.json")})
        assert "peNormalizedAnnual" not in finnhub.fetch_metrics("AAPL")

    def test_metric_units_are_right(self, serve):
        serve({"/stock/metric": load("finnhub_metrics.json")})
        m = finnhub.fetch_metrics("AAPL")
        assert m["peBasicExclExtraTTM"].unit == "x"
        assert m["netProfitMarginTTM"].unit == "%"
        assert m["52WeekHigh"].unit == "USD"

    def test_api_key_never_reaches_the_cache_key(self, monkeypatch):
        """La clave no debe acabar escrita en disco dentro del nombre de caché."""
        seen = {}

        def fake_get(self, url, *, ttl=0, headers=None, cache_key=None):
            seen["url"] = url
            seen["cache_key"] = cache_key
            return load("finnhub_quote.json")

        monkeypatch.setattr("app.providers.http.PoliteClient.get", fake_get)
        finnhub.fetch_quote("AAPL")
        assert "clave-de-prueba" in seen["url"]          # va en la petición
        assert "clave-de-prueba" not in seen["cache_key"]  # pero no en la caché

    def test_news_items_are_labelled_as_interpretation(self, serve):
        serve({"/company-news": load("finnhub_news.json")})
        items = finnhub.fetch_company_news("AAPL")
        assert len(items) == 2
        assert items[0]["published"] == "2026-08-06"
        assert items[1]["published"] is None
        assert all("INTERPRETACIÓN" in i["interpretation_notice"] for i in items)

    def test_quota_error_degrades_to_none_not_to_a_made_up_number(self, serve):
        serve({"/quote": FetchError("429 quota agotada")})
        assert finnhub.fetch_quote("AAPL") is None


# ---------------------------------------------------------------------------
class TestYahooChartParser:
    """Proveedor de precios de respaldo. Existe porque Stooq no es accesible
    desde todas las redes, y sin precios la herramienta no puede opinar."""

    def test_parses_bars_in_order(self, serve):
        serve({"query1.finance.yahoo.com": load("yahoo_chart.json")})
        series = yahoo_chart.fetch_daily("VOO")
        assert len(series.bars) == 6
        assert series.last.day == date(2026, 8, 6)
        assert [b.day for b in series.bars] == sorted(b.day for b in series.bars)

    def test_prefers_adjusted_close(self, serve):
        """El cierre ajustado corrige splits y dividendos; usar el crudo
        distorsionaría medias móviles y rentabilidad a un año."""
        serve({"query1.finance.yahoo.com": load("yahoo_chart.json")})
        series = yahoo_chart.fetch_daily("VOO")
        assert series.bars[0].close == pytest.approx(496.20)   # ajustado
        assert series.bars[0].close != pytest.approx(497.11)   # crudo

    def test_source_is_cited_as_yahoo(self, serve):
        serve({"query1.finance.yahoo.com": load("yahoo_chart.json")})
        series = yahoo_chart.fetch_daily("VOO")
        assert "Yahoo" in series.source.name
        assert series.source.url.startswith("https://")

    def test_gaps_are_dropped_not_filled(self, serve):
        serve({"query1.finance.yahoo.com": load("yahoo_chart_gaps.json")})
        series = yahoo_chart.fetch_daily("XYZ")
        assert len(series.bars) == 3
        assert all(b.close > 0 for b in series.bars)

    def test_delisted_symbol_raises(self, serve):
        serve({"query1.finance.yahoo.com": load("yahoo_chart_error.json")})
        with pytest.raises(FetchError):
            yahoo_chart.fetch_daily("ZZZZ")

    def test_dot_becomes_dash_in_the_symbol(self, monkeypatch):
        seen = {}

        def fake_get(self, url, *, ttl=0, headers=None, cache_key=None):
            seen["url"] = url
            return load("yahoo_chart.json")

        monkeypatch.setattr("app.providers.http.PoliteClient.get", fake_get)
        yahoo_chart.fetch_daily("BRK.B")
        assert "BRK-B" in seen["url"]


class TestPriceFallback:
    """Un solo proveedor caído no puede dejar la herramienta inservible."""

    def test_uses_the_first_provider_that_answers(self, serve):
        serve({"stooq.com": load("stooq_voo.csv"),
               "query1.finance.yahoo.com": load("yahoo_chart.json")})
        series = prices.fetch_daily("VOO")
        assert "Stooq" in series.source.name

    def test_falls_back_when_the_first_is_blocked(self, serve):
        serve({"stooq.com": FetchError("Tunnel connection failed: 403 Forbidden"),
               "query1.finance.yahoo.com": load("yahoo_chart.json")})
        series = prices.fetch_daily("VOO")
        assert "Yahoo" in series.source.name

    def test_citation_names_who_actually_served_it(self, serve):
        """Citar a Stooq un dato que sirvió Yahoo sería una cita falsa."""
        serve({"stooq.com": FetchError("bloqueado"),
               "query1.finance.yahoo.com": load("yahoo_chart.json")})
        series = prices.fetch_daily("VOO")
        assert "Stooq" not in series.source.name

    def test_all_down_raises_listing_every_reason(self, serve):
        serve({"stooq.com": FetchError("403 Forbidden"),
               "query1.finance.yahoo.com": FetchError("timeout")})
        with pytest.raises(FetchError) as err:
            prices.fetch_daily("VOO")
        assert "Stooq" in str(err.value) and "Yahoo" in str(err.value)

    def test_order_is_configurable(self, serve, monkeypatch):
        monkeypatch.setenv("PRICE_PROVIDERS", "yahoo,stooq")
        serve({"stooq.com": load("stooq_voo.csv"),
               "query1.finance.yahoo.com": load("yahoo_chart.json")})
        assert "Yahoo" in prices.fetch_daily("VOO").source.name

    def test_a_single_provider_can_be_forced(self, serve, monkeypatch):
        monkeypatch.setenv("PRICE_PROVIDERS", "yahoo")
        serve({"stooq.com": load("stooq_voo.csv"),
               "query1.finance.yahoo.com": load("yahoo_chart.json")})
        assert prices.order() == ["yahoo"]
        assert "Yahoo" in prices.fetch_daily("VOO").source.name

    def test_bad_value_falls_back_to_the_default_order(self, monkeypatch):
        monkeypatch.setenv("PRICE_PROVIDERS", "inventado,otro")
        assert prices.order() == prices.DEFAULT_ORDER

    def test_probe_reports_every_provider(self, serve):
        serve({"stooq.com": FetchError("403"),
               "query1.finance.yahoo.com": load("yahoo_chart.json")})
        resultados = prices.probe("VOO")
        assert len(resultados) == 2
        assert [r["ok"] for r in resultados] == [False, True]
        assert resultados[0]["error"]


class TestTwelveDataParser:
    """Tercer proveedor de precios, opcional y con clave."""

    @pytest.fixture(autouse=True)
    def _enable(self, monkeypatch):
        monkeypatch.setenv("TWELVEDATA_API_KEY", "clave-de-prueba")

    def test_disabled_without_a_key(self, monkeypatch, serve):
        monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
        monkeypatch.setattr(twelvedata, "api_key", lambda: "")
        serve({})
        assert twelvedata.enabled() is False
        with pytest.raises(FetchError) as err:
            twelvedata.fetch_daily("VOO")
        assert "opcional" in str(err.value).lower()

    def test_parses_and_sorts_oldest_first(self, serve):
        serve({"api.twelvedata.com": load("twelvedata.json")})
        series = twelvedata.fetch_daily("VOO")
        assert [b.day for b in series.bars] == sorted(b.day for b in series.bars)
        assert series.last.close == pytest.approx(501.77)

    def test_unparsable_fields_fall_back_to_the_close(self, serve):
        """Una fila con open/high ilegibles conserva su cierre real en vez de
        descartarse o rellenarse con cero."""
        serve({"api.twelvedata.com": load("twelvedata.json")})
        series = twelvedata.fetch_daily("VOO")
        primera = series.bars[0]
        assert primera.close == pytest.approx(500.85)
        assert primera.open == pytest.approx(500.85)

    def test_a_quota_error_arriving_with_http_200_is_detected(self, serve):
        """Twelve Data devuelve los errores con status 200 y status:error dentro."""
        serve({"api.twelvedata.com": load("twelvedata_error.json")})
        with pytest.raises(FetchError) as err:
            twelvedata.fetch_daily("VOO")
        assert "API credits" in str(err.value)

    def test_the_key_never_reaches_the_cache_key(self, monkeypatch):
        seen = {}

        def fake_get(self, url, *, ttl=0, headers=None, cache_key=None):
            seen["url"] = url
            seen["cache_key"] = cache_key
            return load("twelvedata.json")

        monkeypatch.setattr("app.providers.http.PoliteClient.get", fake_get)
        twelvedata.fetch_daily("VOO")
        assert "clave-de-prueba" in seen["url"]
        assert "clave-de-prueba" not in seen["cache_key"]

    def test_it_is_last_in_the_default_order(self, monkeypatch):
        """Su cuota diaria solo debe gastarse si los que no tienen clave fallan."""
        monkeypatch.setattr(prices.twelvedata, "enabled", lambda: True)
        monkeypatch.setattr(prices, "setting", lambda name, default="": "")
        assert prices.order()[-1] == "twelvedata"

    def test_it_is_skipped_entirely_when_not_configured(self, monkeypatch):
        """Un proveedor con clave sin configurar no debe ni intentarse: fallaria
        siempre y solo anadiria ruido al diagnostico."""
        monkeypatch.setattr(prices.twelvedata, "enabled", lambda: False)
        monkeypatch.setattr(prices, "setting", lambda name, default="": "")
        assert "twelvedata" not in prices.order()
