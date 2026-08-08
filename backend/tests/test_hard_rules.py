"""
Tests de las REGLAS DURAS.

No son tests de "funciona más o menos": comprueban que el producto es incapaz
de incumplir sus propias promesas. Si alguno de estos falla, la herramienta no
debería usarse.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.core.datapoint import DataPoint, Missing, Source, user_source
from app.core.guards import (
    BROKER_EXECUTION_MARKERS,
    HardRuleViolation,
    assert_no_pressure_language,
    assert_numbers_are_cited,
    assert_recommendation_complete,
    collect_allowed_numbers,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _dp(value: float, label: str = "Precio", unit: str = "USD") -> DataPoint:
    return DataPoint(
        label=label,
        value=value,
        unit=unit,
        as_of=date(2026, 8, 1),
        source=Source(name="Fuente de prueba", url="https://example.invalid"),
    )


# ---------------------------------------------------------------------------
# Regla 1: nunca un número sin cita
# ---------------------------------------------------------------------------
class TestNoInventedNumbers:
    def test_cited_number_passes(self):
        allowed = collect_allowed_numbers([_dp(123.45)])
        assert_numbers_are_cited("El precio fue 123.45 dólares.", allowed, "prueba")

    def test_uncited_number_is_blocked(self):
        allowed = collect_allowed_numbers([_dp(123.45)])
        with pytest.raises(HardRuleViolation) as err:
            assert_numbers_are_cited("Subirá un 40 % este año.", allowed, "tesis")
        assert err.value.rule == "ANTI-INVENCION"
        assert "40" in err.value.detail

    def test_missing_datum_contributes_no_allowed_numbers(self):
        allowed = collect_allowed_numbers(
            [Missing(label="PER", reason="No hay cobertura para este símbolo.")]
        )
        with pytest.raises(HardRuleViolation):
            assert_numbers_are_cited("Su PER es 22.", allowed, "evidencia")

    def test_concept_names_with_digits_are_allowed(self):
        # "media de 200 días" nombra un concepto, no afirma un dato del activo.
        allowed = collect_allowed_numbers([])
        assert_numbers_are_cited(
            "Cotiza por encima de su media de 200 días y cerca de su máximo de 52 semanas.",
            allowed,
            "prueba",
        )

    def test_thousands_separator_variants_match(self):
        allowed = collect_allowed_numbers([_dp(1234567.0, label="Ingresos")])
        assert_numbers_are_cited("Ingresó 1,234,567 dólares.", allowed, "prueba")

    def test_datapoint_always_carries_source_and_date(self):
        d = _dp(10.0).to_dict()
        assert d["source_name"]
        assert d["as_of"]
        assert d["citation"]

    def test_missing_states_reason_instead_of_zero(self):
        m = Missing(label="Margen", reason="El proveedor no cubre ETFs.").to_dict()
        assert m["kind"] == "missing"
        assert m["reason"]
        assert "value" not in m


# ---------------------------------------------------------------------------
# Regla 2: ninguna recomendación sin riesgos ni contra-argumento
# ---------------------------------------------------------------------------
class TestRecommendationCompleteness:
    GOOD = dict(
        thesis="Un fondo amplio que encaja con tu plan.",
        risks=["Puede caer con el mercado entero."],
        counter_argument=(
            "El contra-caso más fuerte es que el pasado del precio no predice el futuro "
            "y podrías estar comprando caro."
        ),
        confidence_basis=["Precio reciente de una fuente citada."],
        portfolio_fit="Aporta diversificación donde vas corto.",
    )

    def test_complete_recommendation_passes(self):
        assert_recommendation_complete(**self.GOOD)

    def test_no_risks_is_blocked(self):
        payload = {**self.GOOD, "risks": []}
        with pytest.raises(HardRuleViolation) as err:
            assert_recommendation_complete(**payload)
        assert err.value.rule == "COMPLETITUD"

    def test_blank_risks_are_blocked(self):
        payload = {**self.GOOD, "risks": ["   ", ""]}
        with pytest.raises(HardRuleViolation):
            assert_recommendation_complete(**payload)

    def test_no_counter_argument_is_blocked(self):
        payload = {**self.GOOD, "counter_argument": ""}
        with pytest.raises(HardRuleViolation):
            assert_recommendation_complete(**payload)

    def test_token_counter_argument_is_blocked(self):
        payload = {**self.GOOD, "counter_argument": "Podría bajar."}
        with pytest.raises(HardRuleViolation):
            assert_recommendation_complete(**payload)

    def test_confidence_without_basis_is_blocked(self):
        payload = {**self.GOOD, "confidence_basis": []}
        with pytest.raises(HardRuleViolation):
            assert_recommendation_complete(**payload)

    def test_missing_portfolio_fit_is_blocked(self):
        payload = {**self.GOOD, "portfolio_fit": ""}
        with pytest.raises(HardRuleViolation):
            assert_recommendation_complete(**payload)


# ---------------------------------------------------------------------------
# Regla 3: nada de urgencia ni FOMO
# ---------------------------------------------------------------------------
class TestNoPressureLanguage:
    @pytest.mark.parametrize(
        "text",
        [
            "¡Compra ya antes de que suba!",
            "Es una oportunidad única.",
            "Urgente: revisa esto.",
            "Última oportunidad del año.",
            "Rentabilidad garantizada.",
            "No te lo pierdas.",
            "Esta acción se dispara.",
            "Seguro que sube.",
        ],
    )
    def test_pressure_is_blocked(self, text):
        with pytest.raises(HardRuleViolation) as err:
            assert_no_pressure_language(text, "prueba")
        assert err.value.rule == "ANTI-FOMO"

    @pytest.mark.parametrize(
        "text",
        [
            "Esto es algo que vale la pena mirar cuando tengas un rato.",
            "No hay nada que hacer hoy.",
            "Una caída grande puede ser una oportunidad o una señal de deterioro.",
        ],
    )
    def test_calm_framing_passes(self, text):
        assert_no_pressure_language(text, "prueba")

    def test_real_alert_bodies_are_calm(self):
        from app.core.alerts import FRAMING

        assert_no_pressure_language(FRAMING, "encuadre estándar de alertas")


# ---------------------------------------------------------------------------
# Regla 4: solo lectura, nunca ejecuta
# ---------------------------------------------------------------------------
class TestReadOnly:
    def _source_files(self):
        skip = {".git", "node_modules", "__pycache__", ".venv", "dist", ".data_cache"}
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip for part in path.parts):
                continue
            if path.suffix not in (".py", ".js", ".jsx", ".ts", ".tsx"):
                continue
            yield path

    def test_no_broker_execution_code_anywhere(self):
        """Ningún archivo fuente puede contener rastros de ejecución de órdenes."""
        offenders = []
        for path in self._source_files():
            # El propio catálogo de marcadores y este test los mencionan a propósito.
            if path.name in ("guards.py", "test_hard_rules.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for marker in BROKER_EXECUTION_MARKERS:
                if marker in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: '{marker}'")
        assert not offenders, (
            "Se encontraron rastros de ejecución de órdenes. La herramienta debe ser de "
            "solo lectura:\n" + "\n".join(offenders)
        )

    def test_http_client_only_exposes_get(self):
        from app.providers.http import PoliteClient

        write_verbs = {"post", "put", "patch", "delete", "send", "order"}
        methods = {m for m in dir(PoliteClient) if not m.startswith("_")}
        assert "get" in methods
        assert not (methods & write_verbs), (
            f"El cliente HTTP expone métodos de escritura: {methods & write_verbs}"
        )

    def test_no_outbound_write_requests_in_providers(self):
        """Los proveedores no pueden construir peticiones con método distinto de GET."""
        providers = REPO_ROOT / "backend" / "app" / "providers"
        for path in providers.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(r'method\s*=\s*["\'](POST|PUT|PATCH|DELETE)', text), (
                f"{path.name} construye una petición de escritura."
            )

    def test_health_declares_no_broker(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            body = client.get("/api/health").json()
        assert body["read_only"] is True
        assert body["broker_connection"] is None


# ---------------------------------------------------------------------------
# Honestidad sobre datos viejos o ausentes
# ---------------------------------------------------------------------------
class TestHonestyAboutData:
    def test_age_is_exposed(self):
        old = DataPoint(
            label="Precio",
            value=10.0,
            unit="USD",
            as_of=date.today() - timedelta(days=30),
            source=user_source(),
        )
        assert old.to_dict()["age_days"] == 30

    def test_sources_endpoint_declares_what_is_missing(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            body = client.get("/api/data/sources").json()
        assert body["missing_on_purpose"], "Debe declarar explícitamente qué NO tiene."
        names = {m["what"] for m in body["missing_on_purpose"]}
        assert any("entimiento" in n for n in names)
