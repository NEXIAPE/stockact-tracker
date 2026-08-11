"""
Tests de la API con una base de datos temporal y sin red.

Los proveedores se sustituyen por dobles deterministas para que estos tests no
dependan de que Stooq o la SEC estén disponibles.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.datapoint import Source
from app.providers.stooq import Bar, PriceSeries

TODAY = date.today()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.config.DB_PATH", db)
    monkeypatch.setattr("app.db.DB_PATH", db)

    # Doble del proveedor de precios: serie alcista y determinista.
    def fake_daily(ticker: str, ttl=None) -> PriceSeries:
        closes = [80.0 + i * 0.1 for i in range(400)]
        start = TODAY - timedelta(days=len(closes))
        bars = [
            Bar(day=start + timedelta(days=i), open=c, high=c * 1.01, low=c * 0.99,
                close=c, volume=1000)
            for i, c in enumerate(closes)
        ]
        return PriceSeries(
            ticker=ticker.upper(), bars=bars,
            source=Source(name="Stooq (doble de test)", url="https://example.invalid"),
        )

    monkeypatch.setattr("app.providers.prices.fetch_daily", fake_daily)
    monkeypatch.setattr("app.core.portfolio.prices.fetch_daily", fake_daily)
    monkeypatch.setattr("app.core.recommendation.prices.fetch_daily", fake_daily)
    monkeypatch.setattr("app.core.alerts.prices.fetch_daily", fake_daily)

    # Sin red para fundamentales ni noticias.
    from app.providers import edgar

    monkeypatch.setattr(
        "app.core.recommendation.edgar.fetch_fundamentals",
        lambda t, a="accion": edgar.Fundamentals(
            ticker=t, cik=None, company_name=t,
            source=Source(name="SEC EDGAR (doble de test)", url=""),
            unavailable_reason="Sin red en los tests.",
        ),
    )
    monkeypatch.setattr("app.core.recommendation.news_rss.fetch_news", lambda *a, **k: [])
    monkeypatch.setattr("app.core.alerts.news_rss.fetch_news", lambda *a, **k: [])
    monkeypatch.setattr("app.core.recommendation.stockact.fetch_signal", lambda *a, **k: None)

    from app.main import app

    with TestClient(app) as c:
        yield c


PROFILE = {
    "initial_capital": 5000,
    "monthly_contribution": 300,
    "risk_tolerance": "moderado",
    "horizon_years": 20,
    "goals": ["jubilación"],
    "experience": "principiante",
    "emergency_fund_ok": True,
}


class TestOnboarding:
    def test_onboarding_steps_explain_why(self, client):
        steps = client.get("/api/profile/onboarding").json()["steps"]
        assert len(steps) >= 5
        assert all(s["help"] for s in steps), "Cada paso debe explicar por qué se pregunta."

    def test_profile_starts_unconfigured(self, client):
        assert client.get("/api/profile").json()["configured"] is False

    def test_saving_profile_derives_strategy(self, client):
        body = client.post("/api/profile", json=PROFILE).json()
        strategy = body["profile"]["strategy"]
        assert strategy["target_stocks_pct"] + strategy["target_bonds_pct"] == pytest.approx(100.0)
        assert strategy["rationale"]

    def test_invalid_risk_is_rejected(self, client):
        bad = {**PROFILE, "risk_tolerance": "temerario"}
        assert client.post("/api/profile", json=bad).status_code == 422

    def test_endpoints_require_profile_first(self, client):
        r = client.get("/api/briefing")
        assert r.status_code == 409
        assert r.json()["detail"]["error"] == "perfil_no_definido"


class TestPortfolioApi:
    def test_register_and_value_a_holding(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "voo", "shares": 3, "avg_cost": 100, "asset_type": "etf"})
        client.put("/api/portfolio/cash", json={"amount": 500})
        body = client.get("/api/portfolio").json()
        assert body["positions"][0]["ticker"] == "VOO"
        assert body["positions"][0]["price"]["source_name"]
        assert body["total_value"] > 0

    def test_price_carries_source_and_date(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={"ticker": "VTI", "shares": 1, "avg_cost": 50})
        price = client.get("/api/portfolio").json()["positions"][0]["price"]
        assert price["source_name"] and price["as_of"] and price["citation"]

    def test_trade_log_is_a_record_not_an_order(self, client):
        client.post("/api/profile", json=PROFILE)
        r = client.post("/api/portfolio/trades", json={
            "ticker": "VOO", "action": "compra", "shares": 2, "price": 100,
            "traded_on": TODAY.isoformat(),
        })
        assert r.status_code == 200
        assert "bitácora" in r.json()["note"]

    def test_delete_missing_holding_is_404(self, client):
        client.post("/api/profile", json=PROFILE)
        assert client.delete("/api/portfolio/holdings/NOPE").status_code == 404


class TestAnalysis:
    def _setup(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "VOO", "shares": 5, "avg_cost": 90, "asset_type": "etf"})
        client.put("/api/portfolio/cash", json={"amount": 1000})

    def test_recommendation_has_every_mandatory_block(self, client):
        self._setup(client)
        rec = client.get("/api/analyze/VTI").json()
        for field in ("action", "thesis", "evidence", "risks", "counter_argument",
                      "portfolio_fit", "confidence", "suggested_position"):
            assert rec[field], f"Falta el bloque obligatorio: {field}"
        assert rec["action"] in ("comprar", "mantener", "evitar", "vender")

    def test_every_number_in_evidence_is_cited(self, client):
        self._setup(client)
        rec = client.get("/api/analyze/VTI").json()
        for ev in rec["evidence"]:
            for datum in ev["data"]:
                if datum["kind"] == "datapoint":
                    assert datum["source_name"], "Un número sin fuente."
                    assert datum["as_of"], "Un número sin fecha."
                else:
                    assert datum["reason"], "Un dato faltante sin explicación."

    def test_confidence_declares_basis_and_gaps(self, client):
        self._setup(client)
        conf = client.get("/api/analyze/VTI").json()["confidence"]
        assert conf["level"] in ("baja", "media", "alta")
        assert conf["basis"]
        assert conf["data_gaps"], "Debe decir qué le falta."

    def test_notices_are_always_present(self, client):
        self._setup(client)
        notices = client.get("/api/analyze/VTI").json()["notices"]
        assert "solo lectura" in notices["read_only"].lower()
        assert "contador" in notices["not_advice"].lower()

    def test_beginner_gets_warned_about_single_stocks(self, client):
        self._setup(client)
        rec = client.get("/api/analyze/AAPL?asset_type=accion").json()
        text = " ".join(rec["beginner_warnings"] + rec["risks"]).lower()
        assert "una sola empresa" in text or "acciones individuales" in text

    def test_unknown_ticker_says_so_instead_of_guessing(self, client, monkeypatch):
        self._setup(client)
        from app.providers.http import FetchError

        def boom(ticker, ttl=None):
            raise FetchError("símbolo desconocido")

        monkeypatch.setattr("app.core.recommendation.prices.fetch_daily", boom)
        r = client.get("/api/analyze/ZZZZ")
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "sin_datos_suficientes"

    def test_position_size_comes_from_the_plan(self, client):
        self._setup(client)
        sizing = client.get("/api/analyze/VXUS").json()["suggested_position"]
        assert sizing["applies"] is True
        assert sizing["explanation"]


class TestBriefingAndAlerts:
    def _setup(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "VOO", "shares": 5, "avg_cost": 90, "asset_type": "etf"})
        client.put("/api/portfolio/cash", json={"amount": 1000})

    def test_briefing_is_prioritised_and_honest(self, client):
        self._setup(client)
        b = client.get("/api/briefing").json()
        assert b["headline"]
        assert "portfolio" in b and "unread_alerts" in b and "ideas" in b
        assert isinstance(b["data_health"], list)

    def test_briefing_ideas_carry_risks_and_counter(self, client):
        self._setup(client)
        for idea in client.get("/api/briefing").json()["ideas"]:
            assert idea["risks"], "Una idea sin riesgos es un defecto."
            assert idea["counter_argument"], "Una idea sin contra-caso es un defecto."

    def test_alerts_refresh_and_list(self, client):
        self._setup(client)
        client.post("/api/watchlist", json={"ticker": "VTI", "target_buy_price": 999})
        assert client.post("/api/alerts/refresh").status_code == 200
        body = client.get("/api/alerts").json()
        assert "vale la pena mirar" in body["framing"]

    def test_alert_bodies_never_pressure(self, client):
        from app.core.guards import assert_no_pressure_language

        self._setup(client)
        client.post("/api/watchlist", json={"ticker": "VTI", "target_buy_price": 999})
        client.post("/api/alerts/refresh")
        for a in client.get("/api/alerts").json()["alerts"]:
            assert_no_pressure_language(a["title"], "título")
            assert_no_pressure_language(a["body"], "cuerpo")

    def test_alerts_are_not_duplicated(self, client):
        self._setup(client)
        client.post("/api/watchlist", json={"ticker": "VTI", "target_buy_price": 999})
        client.post("/api/alerts/refresh")
        first = len(client.get("/api/alerts").json()["alerts"])
        client.post("/api/alerts/refresh")
        assert len(client.get("/api/alerts").json()["alerts"]) == first


class TestWatchlistAndFacts:
    def test_registered_fact_becomes_cited_data(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/cash", json={"amount": 1000})
        client.post("/api/watchlist", json={"ticker": "VOO"})
        client.post("/api/watchlist/VOO/facts", json={
            "key": "expense_ratio", "value": 0.03, "unit": "%",
            "source_label": "Ficha oficial del emisor",
            "source_url": "https://investor.vanguard.com/investment-products/etfs/profile/voo",
            "as_of": TODAY.isoformat(),
        })
        rec = client.get("/api/analyze/VOO").json()
        labels = [
            d["label"]
            for ev in rec["evidence"] for d in ev["data"]
            if d["kind"] == "datapoint"
        ]
        assert any("Ratio de gastos" in lbl for lbl in labels)

    def test_etf_expense_ratio_is_missing_until_registered(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/cash", json={"amount": 1000})
        rec = client.get("/api/analyze/VOO").json()
        missing = [
            d for ev in rec["evidence"] for d in ev["data"]
            if d["kind"] == "missing" and "Ratio de gastos" in d["label"]
        ]
        assert missing and missing[0]["reason"]

    def test_etf_catalog_contains_no_numbers(self, client):
        etfs = client.get("/api/watchlist/catalog/etfs").json()["etfs"]
        for e in etfs:
            for field in ("name", "issuer", "exposure"):
                assert not any(ch.isdigit() for ch in e[field]) or "500" in e[field], (
                    f"El catálogo no debe contener cifras sin citar: {e[field]}"
                )


class TestDataOwnership:
    def test_export_returns_every_table(self, client):
        client.post("/api/profile", json=PROFILE)
        payload = client.get("/api/data/export").json()
        assert "profile" in payload["tables"]
        assert payload["tables"]["profile"]

    def test_wipe_requires_confirmation(self, client):
        client.post("/api/profile", json=PROFILE)
        assert client.delete("/api/data/wipe").status_code == 400
        assert client.get("/api/profile").json()["configured"] is True

    def test_wipe_deletes_everything(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={"ticker": "VOO", "shares": 1, "avg_cost": 1})
        assert client.request("DELETE", "/api/data/wipe?confirm=BORRAR").status_code == 200
        assert client.get("/api/profile").json()["configured"] is False
        assert client.get("/api/portfolio").json()["positions"] == []


class TestDefectsFoundInManualRun:
    """Regresiones de fallos reales detectados recorriendo la app a mano."""

    def _setup(self, client, cash=1200):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "VOO", "shares": 6, "avg_cost": 390, "asset_type": "etf"})
        client.put("/api/portfolio/cash", json={"amount": cash})

    def test_bond_fund_is_not_described_as_buying_companies(self, client):
        """BND es un fondo de BONOS: decir que 'compra empresas' es falso."""
        self._setup(client)
        rec = client.get("/api/analyze/BND").json()
        assert "empresas a la vez" not in rec["thesis"]
        assert "bonos" in rec["thesis"].lower()

    def test_bond_fund_risks_are_about_bonds(self, client):
        self._setup(client)
        risks = " ".join(client.get("/api/analyze/BND").json()["risks"]).lower()
        assert "tipos de interés" in risks
        assert "dejar de pagar" in risks

    def test_stock_etf_still_described_as_equities(self, client):
        self._setup(client)
        rec = client.get("/api/analyze/VXUS").json()
        assert "empresas" in rec["thesis"].lower()

    def test_sizing_never_spends_the_minimum_cash_cushion(self, client):
        """Sugerir gastar hasta el último dólar incumpliría la propia estrategia."""
        self._setup(client, cash=1200)
        body = client.get("/api/analyze/VXUS").json()
        sizing = body["suggested_position"]
        strategy = client.get("/api/profile").json()["profile"]["strategy"]
        total = client.get("/api/portfolio").json()["total_value"]
        reserve = strategy["min_cash_pct"] / 100.0 * total
        if sizing["applies"] and sizing["amount_usd"] > 0:
            assert sizing["amount_usd"] <= 1200 - reserve + 0.01, (
                "El importe sugerido se come el colchón mínimo de efectivo."
            )

    def test_sizing_is_zero_when_only_the_cushion_remains(self, client):
        self._setup(client, cash=1)
        sizing = client.get("/api/analyze/VXUS").json()["suggested_position"]
        assert sizing["amount_usd"] == 0
        assert "colchón" in sizing["explanation"]

    def test_multiple_ideas_declare_sizing_is_not_additive(self, client):
        """Tres ideas de mil dólares no son tres mil dólares a gastar."""
        self._setup(client)
        body = client.get("/api/ideas?limit=3").json()
        assert "no se suman" in body["sizing_notice"].lower()
        for idea in body["ideas"]:
            assert idea["sizing_is_alternative"] is True

    def test_briefing_carries_the_same_notice(self, client):
        self._setup(client)
        assert "no se suman" in client.get("/api/briefing").json()["ideas_sizing_notice"].lower()

    def test_every_portfolio_deviation_gets_its_own_alert(self, client):
        """Si todos los avisos de cartera comparten título, la deduplicación se
        come todos menos uno y te pierdes avisos sin enterarte."""
        client.post("/api/profile", json=PROFILE)
        # Cartera deliberadamente mala: concentrada, cargada de acciones sueltas,
        # pasada de sector y con exceso de efectivo.
        client.put("/api/portfolio/holdings",
                   json={"ticker": "AAPL", "shares": 50, "avg_cost": 50, "asset_type": "accion"})
        client.put("/api/portfolio/holdings",
                   json={"ticker": "MSFT", "shares": 40, "avg_cost": 50, "asset_type": "accion"})
        client.put("/api/portfolio/cash", json={"amount": 9000})
        client.post("/api/alerts/refresh")

        alerts = [a for a in client.get("/api/alerts").json()["alerts"] if a["kind"] == "cartera"]
        deviations = [
            d for d in client.get("/api/portfolio").json()["deviations"]
            if d["severity"] == "atencion"
        ]
        assert len(alerts) == len(deviations), (
            f"{len(deviations)} desvíos de atención generaron sólo {len(alerts)} alerta(s)."
        )
        # Dos posiciones pasadas de tope comparten título legítimamente; lo que no
        # puede repetirse es el CONTENIDO, porque eso sería el mismo aviso dos veces.
        assert len({a["body"] for a in alerts}) == len(alerts), "Avisos duplicados."

    def test_two_over_weight_sectors_are_two_alerts(self, client):
        from datetime import date as _date

        from app.core.alerts import Alert

        title = "Un sector concentra más peso del que marca tu estrategia"
        a = Alert(kind="cartera", ticker="", subject="sector|Peso del sector Tecnología",
                  title=title, body="Tecnología pesa de más.", day=_date(2026, 8, 8))
        b = Alert(kind="cartera", ticker="", subject="sector|Peso del sector Salud",
                  title=title, body="Salud pesa de más.", day=_date(2026, 8, 8))
        assert a.fingerprint() != b.fingerprint(), (
            "Dos sectores distintos pasados de tope deben ser dos avisos, no uno."
        )
        # El mismo aviso el mismo día sí debe colapsar.
        again = Alert(kind="cartera", ticker="", subject="sector|Peso del sector Salud",
                      title=title, body="Salud pesa de más.", day=_date(2026, 8, 8))
        assert b.fingerprint() == again.fingerprint()


class TestThesis:
    """La razon por la que compraste es la unica senal de venta que vale.

    Sin ella, opinar sobre vender solo puede apoyarse en el precio, que es
    justo la peor senal posible.
    """

    def _hold(self, client, **extra):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/cash", json={"amount": 1000})
        payload = {"ticker": "VOO", "shares": 5, "avg_cost": 90, "asset_type": "etf"}
        payload.update(extra)
        return client.put("/api/portfolio/holdings", json=payload)

    def test_registering_without_a_thesis_warns(self, client):
        body = self._hold(client).json()
        assert body["thesis_missing"] is True
        assert "precio" in body["note"].lower()

    def test_a_thesis_can_be_saved_with_the_holding(self, client):
        body = self._hold(
            client,
            thesis="Quiero exposición al mercado entero sin elegir empresas.",
            invalidation="Si aparece un fondo equivalente mucho más barato.",
        ).json()
        assert body["thesis_missing"] is False

    def test_updating_shares_does_not_erase_the_thesis(self, client):
        """Cambiar el número de participaciones no puede borrar por qué compraste."""
        self._hold(client, thesis="Mercado entero, sin elegir empresas.")
        self._hold(client, shares=9)  # sin volver a mandar la tesis
        theses = client.get("/api/portfolio/thesis").json()["theses"]
        assert theses[0]["text"] == "Mercado entero, sin elegir empresas."

    def test_the_analysis_shows_your_thesis_back_to_you(self, client):
        self._hold(client, thesis="Mercado entero.", invalidation="Si sube mucho la comisión.")
        review = client.get("/api/analyze/VOO").json()["thesis_review"]
        assert review["has_thesis"] is True
        assert review["thesis"] == "Mercado entero."
        assert review["question"]

    def test_a_missing_thesis_is_reported_as_a_gap(self, client):
        self._hold(client)
        rec = client.get("/api/analyze/VOO").json()
        assert rec["thesis_review"]["has_thesis"] is False
        assert any("no anotaste" in g.lower() for g in rec["confidence"]["data_gaps"])

    def test_the_tool_does_not_claim_to_judge_your_thesis(self, client):
        self._hold(client, thesis="Creo en el mercado a largo plazo.")
        review = client.get("/api/analyze/VOO").json()["thesis_review"]
        assert "no juzga" in review["explanation"].lower()

    def test_reviewing_records_the_date(self, client):
        self._hold(client, thesis="Mercado entero.")
        r = client.put("/api/portfolio/holdings/VOO/thesis",
                       json={"thesis": "Mercado entero, revisado.", "invalidation": "",
                             "mark_reviewed": True})
        assert r.json()["thesis"]["reviewed_at"] == TODAY.isoformat()
        assert r.json()["thesis"]["days_since_review"] == 0

    def test_thesis_for_an_unknown_holding_is_404(self, client):
        client.post("/api/profile", json=PROFILE)
        assert client.put("/api/portfolio/holdings/NOPE/thesis",
                          json={"thesis": "x"}).status_code == 404

    def test_briefing_surfaces_missing_theses(self, client):
        self._hold(client)
        notes = client.get("/api/briefing?include_ideas=false").json()["thesis_notes"]
        assert any("VOO" in n for n in notes)

    def test_no_analysis_for_something_you_do_not_hold_asks_about_thesis(self, client):
        """Solo tiene sentido preguntar por la tesis de lo que ya tienes."""
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/cash", json={"amount": 1000})
        assert client.get("/api/analyze/VTI").json()["thesis_review"] is None


class TestPerformance:
    """La pregunta incomoda: te habria ido mejor comprando el indice y ya."""

    def _setup(self, client, trades=()):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "VOO", "shares": 10, "avg_cost": 80, "asset_type": "etf"})
        client.put("/api/portfolio/cash", json={"amount": 500})
        for t in trades:
            client.post("/api/portfolio/trades", json=t)

    def test_without_trades_it_says_it_cannot_compare(self, client):
        self._setup(client)
        body = client.get("/api/portfolio/performance").json()
        assert body["difference_pct"] is None
        assert "no puedo comparar" in " ".join(body["notes"]).lower()

    def test_it_does_not_invent_a_comparison_from_average_cost(self, client):
        """Sin fechas la comparacion seria falsa; mejor decirlo."""
        self._setup(client)
        body = client.get("/api/portfolio/performance").json()
        assert body["benchmark_value"] is None
        assert body["contributed"] is None

    def test_with_trades_it_compares_against_the_benchmark(self, client):
        hace_dos_anos = (TODAY - timedelta(days=730)).isoformat()
        self._setup(client, trades=[
            {"ticker": "VOO", "action": "compra", "shares": 10, "price": 80,
             "traded_on": hace_dos_anos},
        ])
        body = client.get("/api/portfolio/performance").json()
        assert body["contributed"] == pytest.approx(800.0)
        assert body["benchmark_value"] is not None
        assert body["difference_pct"] is not None

    def test_a_sale_counts_as_money_taken_out(self, client):
        dia = (TODAY - timedelta(days=400)).isoformat()
        self._setup(client, trades=[
            {"ticker": "VOO", "action": "compra", "shares": 10, "price": 100, "traded_on": dia},
            {"ticker": "VOO", "action": "venta", "shares": 4, "price": 100, "traded_on": dia},
        ])
        body = client.get("/api/portfolio/performance").json()
        assert body["contributed"] == pytest.approx(600.0)

    def test_a_short_history_refuses_to_draw_conclusions(self, client):
        ayer = (TODAY - timedelta(days=1)).isoformat()
        self._setup(client, trades=[
            {"ticker": "VOO", "action": "compra", "shares": 1, "price": 100, "traded_on": ayer},
        ])
        veredicto = client.get("/api/portfolio/performance").json()["verdict"].lower()
        assert "poco tiempo" in veredicto or "suerte" in veredicto

    def test_an_invalid_comparison_hides_its_ingredients_too(self, client):
        """Bloquear el porcentaje pero mostrar aportado y valor actual uno al
        lado del otro deja que cualquiera haga la division y saque justo la
        cifra enganosa que se pretendia evitar."""
        dia = (TODAY - timedelta(days=400)).isoformat()
        self._setup(client, trades=[
            {"ticker": "VOO", "action": "compra", "shares": 10, "price": 100, "traded_on": dia},
        ])
        # VOO esta en la bitacora, pero se anade otra posicion que no lo esta.
        client.put("/api/portfolio/holdings",
                   json={"ticker": "AAPL", "shares": 5, "avg_cost": 100, "asset_type": "accion"})

        body = client.get("/api/portfolio/performance").json()
        assert body["comparable"] is False
        assert body["contributed"] is None, "No debe mostrarse lo aportado."
        assert body["current_value"] is None, "Ni el valor actual: juntos permiten la division."
        assert body["benchmark_value"] is None
        etiquetas = [d["label"] for d in body["data"]]
        assert all("aportado" not in e.lower() for e in etiquetas)
        assert any(d["kind"] == "missing" and "AAPL" in d["reason"] for d in body["data"])

    def test_the_method_is_explained(self, client):
        self._setup(client)
        assert "mismo día" in client.get("/api/portfolio/performance").json()["method"]

    def test_every_figure_is_cited(self, client):
        dia = (TODAY - timedelta(days=400)).isoformat()
        self._setup(client, trades=[
            {"ticker": "VOO", "action": "compra", "shares": 10, "price": 100, "traded_on": dia},
        ])
        for d in client.get("/api/portfolio/performance").json()["data"]:
            if d["kind"] == "datapoint":
                assert d["source_name"] and d["as_of"]
            else:
                assert d["reason"]


class TestTodaySummary:
    """Al abrir debe saberse en una linea si hay algo que hacer o no.

    Decir «hoy no hay nada que hacer» alto y claro es una funcion del producto:
    una herramienta que cada manana parece tener algo urgente acaba ensenandote
    a operar de mas.
    """

    def test_an_empty_portfolio_says_where_to_start(self, client):
        client.post("/api/profile", json=PROFILE)
        hoy = client.get("/api/briefing?include_ideas=false").json()["today"]
        assert hoy["status"] == "empezar"
        assert hoy["items"][0]["where"] == "/cartera"

    def test_a_tidy_portfolio_says_there_is_nothing_to_do(self, client):
        client.post("/api/profile", json=PROFILE)
        strategy = client.get("/api/profile").json()["profile"]["strategy"]
        acciones = strategy["target_stocks_pct"]
        client.put("/api/portfolio/holdings", json={
            "ticker": "VTI", "shares": acciones, "avg_cost": 1, "asset_type": "etf",
            "thesis": "Mercado entero de EE.UU.",
        })
        client.put("/api/portfolio/holdings", json={
            "ticker": "BND", "shares": 100 - acciones, "avg_cost": 1, "asset_type": "etf",
            "thesis": "Bonos para amortiguar caídas.",
        })
        client.put("/api/portfolio/cash", json={"amount": 5})
        hoy = client.get("/api/briefing?include_ideas=false").json()["today"]
        assert hoy["status"] == "nada_que_hacer"
        assert hoy["items"] == []
        assert "normal" in hoy["explanation"].lower()

    def test_problems_are_listed_with_where_to_go(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "AAPL", "shares": 100, "avg_cost": 1, "asset_type": "accion"})
        client.put("/api/portfolio/cash", json={"amount": 0})
        hoy = client.get("/api/briefing?include_ideas=false").json()["today"]
        assert hoy["status"] == "algo_que_mirar"
        assert hoy["items"]
        assert all(i["where"].startswith("/") for i in hoy["items"])

    def test_it_never_sounds_urgent(self, client):
        from app.core.guards import assert_no_pressure_language

        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "AAPL", "shares": 100, "avg_cost": 1, "asset_type": "accion"})
        hoy = client.get("/api/briefing?include_ideas=false").json()["today"]
        # La propiedad que importa: NINGUN texto de este bloque puede sonar a
        # urgencia, ni el titular, ni la explicacion, ni los enlaces.
        assert_no_pressure_language(hoy["headline"], "titular del día")
        assert_no_pressure_language(hoy["explanation"], "explicación del día")
        for item in hoy["items"]:
            assert_no_pressure_language(item["text"], "elemento del día")
        # Y debe decir explicitamente que no hay que actuar hoy.
        assert "actúes hoy" in hoy["explanation"].lower()

    def test_at_most_four_items_so_it_stays_scannable(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings",
                   json={"ticker": "AAPL", "shares": 100, "avg_cost": 1, "asset_type": "accion"})
        client.put("/api/portfolio/holdings",
                   json={"ticker": "MSFT", "shares": 100, "avg_cost": 1, "asset_type": "accion"})
        client.post("/api/alerts/refresh")
        hoy = client.get("/api/briefing?include_ideas=false").json()["today"]
        assert len(hoy["items"]) <= 4


# ---------------------------------------------------------------------------
class TestPortfolioLoadsWithoutTheNetwork:
    """La cartera local no puede quedar secuestrada por una llamada remota.

    Cuántas participaciones tienes, a qué coste y cuánto efectivo te queda
    están en tu disco. Medido con la red caída, la pantalla tardaba 25 segundos
    en mostrarlos porque esperaba a los precios. Ahora hay una fase local.
    """

    def _setup(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "VTI", "shares": 30, "avg_cost": 240, "asset_type": "etf"})
        client.put("/api/portfolio/cash", json={"amount": 2500})

    def test_your_own_numbers_come_back_without_asking_for_prices(self, client):
        self._setup(client)
        d = client.get("/api/portfolio?with_prices=false").json()
        assert d["cash"] == 2500
        pos = d["positions"][0]
        assert pos["ticker"] == "VTI"
        assert pos["shares"] == 30
        assert pos["avg_cost"] == 240
        assert pos["cost_basis"] == 7200

    def test_it_does_not_touch_the_network(self, client, monkeypatch):
        """Si algo llama al proveedor en la fase local, el test estalla."""
        self._setup(client)

        def prohibido(*a, **k):
            raise AssertionError("La fase local pidió un precio; no debe.")

        monkeypatch.setattr("app.core.portfolio.prices.fetch_daily", prohibido)
        r = client.get("/api/portfolio?with_prices=false")
        assert r.status_code == 200

    def test_pending_is_never_dressed_up_as_failed(self, client):
        """La regla dura aquí.

        Decir «no se pudo obtener el precio» cuando ni siquiera se ha pedido es
        inventarse un fallo. Y decir que un valor es cero, peor.
        """
        self._setup(client)
        d = client.get("/api/portfolio?with_prices=false").json()

        assert d["prices_pending"] is True
        assert d["missing_prices"] == []
        assert d["data_warning"] == ""
        assert d["positions"][0]["price_pending"] is True
        assert d["positions"][0]["price_error"] == ""
        # Nada de ceros de relleno donde falta el dato.
        assert d["total_value"] is None
        assert d["positions"][0]["market_value"] is None
        assert d["positions"][0]["unrealized_gain"] is None

    def test_no_deviations_are_invented_without_weights(self, client):
        """Sin precios no hay pesos, y sin pesos un desvío no significa nada."""
        self._setup(client)
        assert client.get("/api/portfolio?with_prices=false").json()["deviations"] == []

    def test_the_valued_version_still_works_as_before(self, client):
        self._setup(client)
        d = client.get("/api/portfolio").json()
        assert d["prices_pending"] is False
        assert d["positions"][0]["price_pending"] is False
        assert d["positions"][0]["market_value"] is not None
        assert d["total_value"] is not None


# ---------------------------------------------------------------------------
class TestBriefingLoadsWithoutTheNetwork:
    """El briefing tampoco puede quedarse en blanco esperando a la red.

    Pero aquí hay una trampa que no existía en la cartera: esta pantalla
    responde «¿hay algo que hacer hoy?», y esa respuesta es en la que el
    usuario confía para no leer el resto. Darla a medias es peor que tardar.
    """

    def _setup(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "AAPL", "shares": 100, "avg_cost": 1, "asset_type": "accion"})

    def test_what_is_already_known_comes_back_at_once(self, client):
        self._setup(client)
        d = client.get("/api/briefing?include_ideas=false&with_prices=false").json()
        assert d["prices_pending"] is True
        # Las alertas y las tesis están guardadas: no necesitan red.
        assert "unread_alerts" in d
        assert d["portfolio"]["positions"][0]["shares"] == 100

    def test_it_does_not_touch_the_network(self, client, monkeypatch):
        self._setup(client)

        def prohibido(*a, **k):
            raise AssertionError("La fase local del briefing pidió un precio.")

        monkeypatch.setattr("app.core.portfolio.prices.fetch_daily", prohibido)
        r = client.get("/api/briefing?include_ideas=false&with_prices=false")
        assert r.status_code == 200

    def test_it_never_says_there_is_nothing_to_do_before_checking(self, client):
        """LA REGLA DURA DE ESTA PANTALLA.

        Sin precios no se han podido comprobar los desvíos, que son la mitad de
        lo que responde la pregunta. Decir «hoy no hay nada que hacer» habiendo
        mirado la mitad no es ser rápido: es afirmar algo que no se sabe.
        """
        self._setup(client)   # sin alertas ni nada pendiente: el caso peligroso
        hoy = client.get(
            "/api/briefing?include_ideas=false&with_prices=false"
        ).json()["today"]

        assert hoy["status"] == "comprobando"
        assert "nada que hacer" not in hoy["headline"].lower()
        assert "nada que hacer" not in hoy["explanation"].lower()
        # Y debe decir QUÉ le falta, no sólo callarse.
        assert "precio" in hoy["explanation"].lower()

    def test_once_valued_it_answers_the_question_for_real(self, client):
        self._setup(client)
        hoy = client.get("/api/briefing?include_ideas=false").json()["today"]
        assert hoy["status"] in ("nada_que_hacer", "algo_que_mirar")

    def test_no_deviations_are_invented_without_weights(self, client):
        self._setup(client)
        d = client.get("/api/briefing?include_ideas=false&with_prices=false").json()
        assert d["deviations"] == []

    def test_the_local_phase_is_not_logged_as_a_run(self, client):
        """Tres peticiones por pantalla no pueden ser tres briefings en la bitácora."""
        self._setup(client)
        from app.db import get_conn

        def ejecuciones():
            with get_conn() as conn:
                return conn.execute(
                    "SELECT COUNT(*) c FROM runs WHERE kind = 'briefing'"
                ).fetchone()["c"]

        antes = ejecuciones()
        client.get("/api/briefing?include_ideas=false&with_prices=false")
        assert ejecuciones() == antes, "La fase local no revisó la cartera."
        client.get("/api/briefing?include_ideas=false")
        assert ejecuciones() == antes + 1

    def test_the_anti_fomo_guard_also_covers_the_new_state(self, client):
        from app.core.guards import assert_no_pressure_language

        self._setup(client)
        hoy = client.get(
            "/api/briefing?include_ideas=false&with_prices=false"
        ).json()["today"]
        assert_no_pressure_language(hoy["headline"], "titular comprobando")
        assert_no_pressure_language(hoy["explanation"], "explicación comprobando")


# ---------------------------------------------------------------------------
class TestCheaperMakesNoPromises:
    """La pantalla «más barato que hace poco».

    Nacio de una peticion cuya premisa era falsa: "cosas que caen y se sabe que
    volveran a subir". Eso no se sabe de ningun activo. La pantalla existe, pero
    solo puede afirmar un hecho comprobable —cuanto ha caido— y tiene prohibido
    insinuar el resto. Estos tests son ese limite.
    """

    PROHIBIDO = [
        "volvera a subir", "volverá a subir", "va a subir", "se recuperara",
        "se recuperará", "rebotara", "rebotará", "suele rebotar",
        "objetivo de precio", "precio objetivo", "garantiza", "seguro que",
        "no puede bajar mas", "no puede bajar más", "esta barato",
    ]

    def _textos(self, payload) -> list:
        """Todo el texto que la pantalla puede mostrar, venga de donde venga."""
        salida = []

        def recorrer(nodo):
            if isinstance(nodo, str):
                salida.append(nodo)
            elif isinstance(nodo, dict):
                for k, v in nodo.items():
                    # Los titulares son de terceros: no los escribimos nosotros
                    # y no podemos responder de sus palabras. Se excluyen a
                    # proposito, y por eso van etiquetados como interpretacion.
                    if k == "news":
                        continue
                    # El descargo cuyo trabajo es ENUMERAR lo que no hay tiene
                    # que nombrar esas frases para negarlas. Buscarle las
                    # palabras seria como prohibir la palabra "veneno" en la
                    # etiqueta que avisa de que no lleva. Se verifica aparte,
                    # con la regla que le corresponde: ver el test siguiente.
                    if k == "no_forecast_notice":
                        continue
                    recorrer(v)
            elif isinstance(nodo, list):
                for v in nodo:
                    recorrer(v)

        recorrer(payload)
        return salida

    def test_it_never_predicts_a_recovery(self, client):
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "AAPL", "shares": 10, "avg_cost": 1, "asset_type": "accion"})
        payload = client.get("/api/cheaper?with_news=false").json()

        for texto in self._textos(payload):
            bajo = texto.lower()
            for frase in self.PROHIBIDO:
                assert frase not in bajo, (
                    f"La pantalla insinua una recuperacion: {frase!r} en {texto!r}. "
                    "Nadie sabe si algo que bajo volvera a subir."
                )

    def test_it_says_out_loud_that_it_does_not_predict(self, client):
        """El descargo, verificado por lo que DEBE decir en vez de por lo que no.

        Es el unico texto exento del barrido de frases prohibidas, asi que su
        contenido se fija aqui: tiene que negar explicitamente que se sepa el
        futuro, no limitarse a evitar ciertas palabras.
        """
        client.post("/api/profile", json=PROFILE)
        aviso = client.get("/api/cheaper?with_news=false").json()["no_forecast_notice"]
        bajo = aviso.lower()
        assert "nadie sabe" in bajo
        assert "no hay ninguna previsi" in bajo
        # Y no puede afirmar lo contrario de lo que dice negar.
        assert "seguro" not in bajo and "garantiz" not in bajo

    def test_no_pressure_language_anywhere(self, client):
        from app.core.guards import assert_no_pressure_language

        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "AAPL", "shares": 10, "avg_cost": 1, "asset_type": "accion"})
        payload = client.get("/api/cheaper?with_news=false").json()
        for texto in self._textos(payload):
            assert_no_pressure_language(texto, "pantalla de caidas")

    def test_a_single_stock_always_carries_the_warning(self, client):
        """En una empresa concreta, la advertencia ES el contenido."""
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "AAPL", "shares": 10, "avg_cost": 1, "asset_type": "accion"})
        d = client.get("/api/cheaper?with_news=false").json()
        for it in d["individual"]:
            assert it["warnings"], f"{it['ticker']} se muestra sin advertencia."
            texto = (it["reading"] + " " + " ".join(it["warnings"])).lower()
            assert "no significa barato" in texto or "no puede distinguir" in texto

    def test_every_number_shown_is_cited(self, client):
        """Regla dura numero uno, tambien aqui."""
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "AAPL", "shares": 10, "avg_cost": 1, "asset_type": "accion"})
        d = client.get("/api/cheaper?with_news=false").json()
        for it in d["broad"] + d["individual"]:
            for campo in ("drawdown", "last_close"):
                dato = it[campo]
                assert dato["kind"] == "datapoint"
                assert dato["source_name"], f"{it['ticker']}.{campo} sin fuente."
                assert dato["as_of"], f"{it['ticker']}.{campo} sin fecha."

    def test_it_is_not_a_market_wide_scanner(self, client):
        """Solo tu universo. Un escaner de lo que mas cae es una lista de
        cuchillos cayendo, y seria el descubrimiento diario que la herramienta
        evita a proposito en todo lo demas."""
        client.post("/api/profile", json=PROFILE)
        client.put("/api/portfolio/holdings", json={
            "ticker": "AAPL", "shares": 10, "avg_cost": 1, "asset_type": "accion"})
        d = client.get("/api/cheaper?with_news=false").json()

        from app.core.universe import BEGINNER_STARTING_UNIVERSE

        permitidos = set(BEGINNER_STARTING_UNIVERSE) | {"AAPL"}
        for it in d["broad"] + d["individual"]:
            assert it["ticker"] in permitidos, (
                f"{it['ticker']} no esta en tu universo: la pantalla se convirtio "
                "en un escaner de mercado."
            )
