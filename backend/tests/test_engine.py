"""
Tests del motor: perfil → estrategia, cartera, indicadores y recomendación.

Todo con datos SINTÉTICOS e inyectados: estos tests no tocan la red, así que
son reproducibles y no golpean fuentes gratuitas.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core import indicators as ind
from app.core.datapoint import DataPoint, Source
from app.core.guards import HardRuleViolation
from app.core.portfolio import PortfolioState, Position, check_deviations
from app.core.profile import Profile, derive_strategy, volatility_ceiling
from app.core.recommendation import enforce_hard_rules
from app.providers.stooq import Bar, PriceSeries

TODAY = date(2026, 8, 7)


def make_series(closes, ticker="TEST"):
    start = TODAY - timedelta(days=len(closes))
    bars = [
        Bar(day=start + timedelta(days=i), open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]
    return PriceSeries(ticker=ticker, bars=bars, source=Source(name="Serie de prueba", url=""))


def make_profile(**over) -> Profile:
    base = dict(
        initial_capital=5000.0,
        monthly_contribution=300.0,
        risk_tolerance="moderado",
        horizon_years=20,
        goals=["jubilación"],
        experience="principiante",
        emergency_fund_ok=True,
        updated_at=TODAY,
    )
    base.update(over)
    return Profile(**base)


# ---------------------------------------------------------------------------
class TestStrategyDerivation:
    def test_conservative_holds_fewer_stocks_than_aggressive(self):
        cons = derive_strategy(make_profile(risk_tolerance="conservador"))
        aggr = derive_strategy(make_profile(risk_tolerance="agresivo"))
        assert cons.target_stocks_pct < aggr.target_stocks_pct

    def test_allocation_always_sums_to_one_hundred(self):
        for risk in ("conservador", "moderado", "agresivo"):
            for years in (1, 3, 7, 12, 25):
                s = derive_strategy(make_profile(risk_tolerance=risk, horizon_years=years))
                assert s.target_stocks_pct + s.target_bonds_pct == pytest.approx(100.0)

    def test_short_horizon_cuts_stock_exposure(self):
        long_h = derive_strategy(make_profile(horizon_years=25))
        short_h = derive_strategy(make_profile(horizon_years=2))
        assert short_h.target_stocks_pct < long_h.target_stocks_pct

    def test_no_emergency_fund_reduces_risk(self):
        with_fund = derive_strategy(make_profile(emergency_fund_ok=True))
        without = derive_strategy(make_profile(emergency_fund_ok=False))
        assert without.target_stocks_pct < with_fund.target_stocks_pct

    def test_beginner_single_stock_cap_is_tight(self):
        s = derive_strategy(make_profile(experience="principiante", risk_tolerance="agresivo"))
        assert s.max_single_stock_pct <= 5.0

    def test_every_rule_is_explained(self):
        s = derive_strategy(make_profile())
        assert s.rationale, "La estrategia debe explicar de dónde sale cada regla."
        assert all(len(r) > 20 for r in s.rationale)

    def test_stock_pct_stays_within_bounds(self):
        for risk in ("conservador", "moderado", "agresivo"):
            for years in (1, 60):
                for fund in (True, False):
                    s = derive_strategy(
                        make_profile(risk_tolerance=risk, horizon_years=years, emergency_fund_ok=fund)
                    )
                    assert 20.0 <= s.target_stocks_pct <= 95.0


# ---------------------------------------------------------------------------
class TestIndicators:
    def test_sma_needs_enough_history(self):
        short = make_series([10.0] * 50)
        assert isinstance(ind.sma(short, 200), type(ind.sma(short, 200)))
        result = ind.sma(short, 200)
        assert result.__class__.__name__ == "Missing"
        assert "200" in result.reason

    def test_sma_of_flat_series_equals_price(self):
        flat = make_series([25.0] * 300)
        avg = ind.sma(flat, 200)
        assert isinstance(avg, DataPoint)
        assert avg.value == pytest.approx(25.0)

    def test_uptrend_is_detected(self):
        rising = make_series([100.0 + i * 0.5 for i in range(300)])
        assert ind.trend_label(rising) == "alcista"

    def test_downtrend_is_detected(self):
        falling = make_series([250.0 - i * 0.5 for i in range(300)])
        assert ind.trend_label(falling) == "bajista"

    def test_flat_series_has_no_volatility(self):
        flat = make_series([50.0] * 300)
        vol = ind.annualized_volatility(flat)
        assert isinstance(vol, DataPoint)
        assert vol.value == pytest.approx(0.0, abs=1e-9)

    def test_drawdown_is_negative_after_a_fall(self):
        series = make_series([100.0] * 200 + [60.0])
        dd = ind.drawdown_from_high(series)
        assert isinstance(dd, DataPoint)
        assert dd.value < -30

    def test_derived_values_declare_their_method(self):
        series = make_series([10.0 + i * 0.01 for i in range(300)])
        avg = ind.sma(series, 50)
        assert "Calculado por la herramienta" in avg.source.name

    def test_daily_change_matches_manual_math(self):
        series = make_series([100.0, 110.0])
        change = ind.daily_change(series)
        assert isinstance(change, DataPoint)
        assert change.value == pytest.approx(10.0)


# ---------------------------------------------------------------------------
def make_state(positions, cash=0.0):
    total = sum(p.market_value or 0.0 for p in positions) + cash
    return PortfolioState(
        positions=positions,
        cash=cash,
        cash_updated=TODAY,
        invested_value=total - cash,
        total_value=total,
        as_of=TODAY,
    )


def make_position(ticker, shares, price, asset_type="accion", avg_cost=None):
    pos = Position(
        ticker=ticker,
        shares=shares,
        avg_cost=avg_cost if avg_cost is not None else price,
        asset_type=asset_type,
    )
    pos.price = DataPoint(
        label="Último cierre", value=price, unit="USD", as_of=TODAY,
        source=Source(name="Serie de prueba", url=""),
    )
    return pos


class TestPortfolio:
    def test_weights_sum_to_one_hundred_without_cash(self):
        state = make_state([
            make_position("AAPL", 10, 100.0),
            make_position("VOO", 10, 100.0, asset_type="etf"),
        ])
        assert sum(state.weights().values()) == pytest.approx(100.0)

    def test_over_concentration_in_single_stock_is_flagged(self):
        profile = make_profile()
        strategy = derive_strategy(profile)
        state = make_state([make_position("TSLA", 100, 100.0)])
        kinds = {d.kind for d in check_deviations(state, profile, strategy)}
        assert "concentracion" in kinds

    def test_diversified_beginner_portfolio_is_not_flagged_for_concentration(self):
        profile = make_profile()
        strategy = derive_strategy(profile)
        stocks_target = strategy.target_stocks_pct
        state = make_state(
            [
                make_position("VTI", 10, stocks_target, asset_type="etf"),
                make_position("BND", 10, 100.0 - stocks_target, asset_type="etf"),
            ],
            cash=0.0,
        )
        kinds = {d.kind for d in check_deviations(state, profile, strategy)}
        assert "concentracion" not in kinds
        assert "acciones_individuales" not in kinds

    def test_too_much_in_individual_stocks_is_flagged_for_beginner(self):
        profile = make_profile(experience="principiante")
        strategy = derive_strategy(profile)
        state = make_state([
            make_position("AAPL", 10, 40.0),
            make_position("MSFT", 10, 40.0),
            make_position("VOO", 10, 20.0, asset_type="etf"),
        ])
        kinds = {d.kind for d in check_deviations(state, profile, strategy)}
        assert "acciones_individuales" in kinds

    def test_missing_price_does_not_count_as_zero(self):
        pos = Position(ticker="XYZ", shares=10, avg_cost=5.0, asset_type="accion")
        pos.price_error = "Fuente caída"
        state = PortfolioState(
            positions=[pos], cash=100.0, cash_updated=TODAY,
            invested_value=None, total_value=None, missing_prices=["XYZ"], as_of=TODAY,
        )
        assert state.total_value is None
        assert "XYZ" in state.missing_prices

    def test_deviation_messages_are_calm(self):
        from app.core.guards import assert_no_pressure_language

        profile = make_profile()
        strategy = derive_strategy(profile)
        state = make_state([make_position("TSLA", 100, 100.0)], cash=500.0)
        for dev in check_deviations(state, profile, strategy):
            assert_no_pressure_language(dev.message, dev.kind)

    def test_individual_stock_pct_ignores_etfs(self):
        state = make_state([
            make_position("AAPL", 1, 50.0),
            make_position("VOO", 1, 50.0, asset_type="etf"),
        ])
        assert state.individual_stock_pct() == pytest.approx(50.0)


# ---------------------------------------------------------------------------
class TestRecommendationGuardIntegration:
    """La recomendación pasa por los guardianes; si se rompe, no se muestra."""

    def _rec(self, **over):
        from app.core.recommendation import Evidence, Recommendation

        base = dict(
            ticker="VOO",
            name="Vanguard S&P 500 ETF",
            asset_type="etf",
            action="comprar",
            action_label="Candidato razonable a compra",
            thesis="Un fondo amplio que encaja con tu plan.",
            suggested_position={"explanation": "Sale de tu propio tope por posición."},
            evidence=[Evidence(claim="Tendencia alcista.", data=[])],
            risks=["Cae si cae el mercado entero."],
            counter_argument=(
                "El contra-caso más fuerte es que el precio pasado no predice el futuro "
                "y comprar lo que ha subido es como se compra caro."
            ),
            portfolio_fit="Aporta diversificación donde vas corto.",
            portfolio_fit_data=[],
            confidence_level="media",
            confidence_basis=["Precio reciente de una fuente citada."],
            data_gaps=[],
            news=[],
            sentiment=None,
            context_signals=[],
            beginner_warnings=[],
            thesis_review=None,
            score=30.0,
            score_breakdown=[{"factor": "Tendencia", "points": 10.0, "note": "Alcista."}],
            as_of=TODAY,
        )
        base.update(over)
        return Recommendation(**base)

    def test_valid_recommendation_passes(self):
        enforce_hard_rules(self._rec())

    def test_recommendation_without_risks_is_blocked(self):
        with pytest.raises(HardRuleViolation):
            enforce_hard_rules(self._rec(risks=[]))

    def test_recommendation_without_counter_is_blocked(self):
        with pytest.raises(HardRuleViolation):
            enforce_hard_rules(self._rec(counter_argument=""))

    def test_uncited_number_in_thesis_is_blocked(self):
        with pytest.raises(HardRuleViolation) as err:
            enforce_hard_rules(self._rec(thesis="Debería rendir un 12,5 % anual."))
        assert err.value.rule == "ANTI-INVENCION"

    def test_pressure_language_in_risk_is_blocked(self):
        with pytest.raises(HardRuleViolation) as err:
            enforce_hard_rules(self._rec(risks=["Compra ya antes de que suba."]))
        assert err.value.rule == "ANTI-FOMO"

    def test_number_backed_by_evidence_passes(self):
        from app.core.recommendation import Evidence

        dp = DataPoint(
            label="Precio", value=512.75, unit="USD", as_of=TODAY,
            source=Source(name="Stooq", url=""),
        )
        enforce_hard_rules(
            self._rec(
                evidence=[Evidence(claim="Cerró a 512.75 dólares.", data=[dp])],
            )
        )


class TestVolatilityCeiling:
    def test_ceiling_grows_with_risk_tolerance(self):
        c = volatility_ceiling(make_profile(risk_tolerance="conservador"))
        m = volatility_ceiling(make_profile(risk_tolerance="moderado"))
        a = volatility_ceiling(make_profile(risk_tolerance="agresivo"))
        assert c < m < a


class TestSourceFailureHonesty:
    """No es lo mismo «no existe» que «no pude preguntar». Confundirlas sería
    afirmar algo falso sobre un dato, que es justo lo que está prohibido."""

    def test_unreachable_sec_is_not_reported_as_unknown_ticker(self, monkeypatch):
        from app.providers import edgar
        from app.providers.http import FetchError

        def boom():
            raise FetchError("proxy bloqueó la conexión")

        monkeypatch.setattr(edgar, "_load_ticker_map", boom)
        result = edgar.fetch_fundamentals("AAPL")
        assert "no se pudo consultar" in result.unavailable_reason.lower()
        assert "no aparece" not in result.unavailable_reason.lower()

    def test_genuinely_unknown_ticker_says_so(self, monkeypatch):
        from app.providers import edgar

        monkeypatch.setattr(edgar, "_load_ticker_map", lambda: {"AAPL": {"cik": 320193, "title": "Apple"}})
        result = edgar.fetch_fundamentals("ZZZZ")
        assert "no aparece" in result.unavailable_reason.lower()

    def test_etf_reason_says_not_applicable(self):
        from app.providers import edgar

        result = edgar.fetch_fundamentals("VOO", "etf")
        assert "no aplica" in result.unavailable_reason.lower()


class TestSellLogic:
    """Cuando vender, y sobre todo cuando NO.

    Regresion de un fallo grave: el marcador mezclaba «merece la pena tener
    esto» con «conviene comprar mas ahora», asi que tener ya el peso objetivo
    que fija la propia estrategia bastaba para recomendar VENDER un activo
    sano. Cumplir tu plan no puede ser motivo para deshacerlo.
    """

    from app.core.recommendation import _decide  # noqa: N805

    def _d(self, **over):
        from app.core.recommendation import _decide

        base = dict(asset_score=0.0, fit_score=0.0, held=True,
                    over_cap=False, deteriorated=False)
        base.update(over)
        return _decide(**base)[0]

    def test_holding_your_exact_target_is_never_a_sell(self):
        # Sin margen para comprar mas (fit muy negativo) pero activo sano.
        assert self._d(asset_score=10, fit_score=-30) == "mantener"

    def test_no_cash_is_never_a_reason_to_sell(self):
        assert self._d(asset_score=5, fit_score=-40) == "mantener"

    def test_a_price_fall_alone_is_not_a_sell(self):
        """Vender por haber caido convierte una perdida temporal en definitiva."""
        assert self._d(asset_score=-40, deteriorated=False) == "mantener"

    def test_real_deterioration_does_trigger_a_sell(self):
        assert self._d(asset_score=-25, deteriorated=True) == "vender"

    def test_mild_deterioration_alone_is_not_enough(self):
        assert self._d(asset_score=-5, deteriorated=True) == "mantener"

    def test_over_concentration_is_trim_not_sell(self):
        assert self._d(asset_score=30, over_cap=True) == "recortar"

    def test_trim_wins_even_over_deterioration(self):
        """Si sobra peso, lo primero es devolverlo a su tamano."""
        assert self._d(asset_score=-30, over_cap=True, deteriorated=True) == "recortar"

    def test_adding_more_needs_both_merit_and_room(self):
        assert self._d(asset_score=30, fit_score=10) == "comprar"
        assert self._d(asset_score=30, fit_score=-5) == "mantener"

    def test_a_new_candidate_needs_merit_and_room(self):
        assert self._d(asset_score=25, fit_score=5, held=False) == "comprar"
        assert self._d(asset_score=25, fit_score=-5, held=False) == "evitar"
        assert self._d(asset_score=-30, fit_score=10, held=False) == "evitar"

    def test_every_action_is_declared(self):
        from app.core.recommendation import ACTIONS

        for accion in ("comprar", "mantener", "recortar", "evitar", "vender"):
            assert accion in ACTIONS


class TestSellingCarriesItsOwnRisks:
    def test_selling_risks_mention_tax_and_finality(self):
        from app.core.recommendation import _selling_risks

        texto = " ".join(_selling_risks()).lower()
        assert "definitiv" in texto
        assert "contador" in texto or "tributari" in texto
