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

    monkeypatch.setattr("app.providers.stooq.fetch_daily", fake_daily)
    monkeypatch.setattr("app.core.portfolio.stooq.fetch_daily", fake_daily)
    monkeypatch.setattr("app.core.recommendation.stooq.fetch_daily", fake_daily)
    monkeypatch.setattr("app.core.alerts.stooq.fetch_daily", fake_daily)

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

        monkeypatch.setattr("app.core.recommendation.stooq.fetch_daily", boom)
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
