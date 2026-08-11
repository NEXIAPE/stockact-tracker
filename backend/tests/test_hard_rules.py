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


class TestConfigFile:
    """La configuracion debe aplicar sin importar como se lance la herramienta.

    Regresion de un fallo real: el email vivia solo en una variable de entorno
    exportada por el script de arranque, asi que ejecutar el diagnostico desde
    otra terminal lo perdia y la herramienta se identificaba ante la SEC con el
    email de ejemplo sin avisar de nada.
    """

    @pytest.fixture(autouse=True)
    def _restore_config(self, monkeypatch):
        """Recargar el modulo de configuracion es global: si no se deshace, el
        .env temporal de un test contamina a todos los demas.

        Y hay que devolverlo al .env FALSO del conftest, no simplemente borrar
        la variable. Borrarla hacia que la recarga apuntara al .env REAL de
        quien ejecutara la suite, y como esta clase va antes que
        test_providers, todos los tests posteriores pasaban a leer su
        configuracion personal. Ese era el origen de dos fallos que solo
        aparecian en la maquina del usuario: su .env fija el orden de
        proveedores y los tests dan por hecho el de por defecto.
        """
        yield
        import importlib

        import conftest
        from app import config as config_mod
        from app.providers import prices

        monkeypatch.setenv("INVEST_ENV_FILE", str(conftest.ENV_FILE_DE_MENTIRA))
        importlib.reload(config_mod)
        importlib.reload(prices)

    def _reload(self, monkeypatch, env_path):
        import importlib

        from app import config as config_mod

        monkeypatch.setenv("INVEST_ENV_FILE", str(env_path))
        return importlib.reload(config_mod)

    def test_reads_values_from_the_env_file(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("INVEST_CONTACT=yo@ejemplo.pe\n", encoding="utf-8")
        monkeypatch.delenv("INVEST_CONTACT", raising=False)
        cfg = self._reload(monkeypatch, env)
        assert cfg.CONTACT_EMAIL == "yo@ejemplo.pe"
        assert "yo@ejemplo.pe" in cfg.USER_AGENT

    def test_real_environment_variable_wins(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("INVEST_CONTACT=archivo@ejemplo.pe\n", encoding="utf-8")
        monkeypatch.setenv("INVEST_CONTACT", "entorno@ejemplo.pe")
        cfg = self._reload(monkeypatch, env)
        assert cfg.CONTACT_EMAIL == "entorno@ejemplo.pe"

    def test_comments_blank_lines_and_quotes_are_handled(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            '# un comentario\n\nFINNHUB_API_KEY="con-comillas"\n  \nsin_igual\n',
            encoding="utf-8",
        )
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        cfg = self._reload(monkeypatch, env)
        assert cfg.FINNHUB_API_KEY == "con-comillas"
        assert cfg.FINNHUB_ENABLED is True

    def test_a_missing_file_does_not_break_startup(self, tmp_path, monkeypatch):
        monkeypatch.delenv("INVEST_CONTACT", raising=False)
        cfg = self._reload(monkeypatch, tmp_path / "no-existe.env")
        assert cfg.CONTACT_EMAIL.endswith("example.com")

    def test_price_provider_order_comes_from_the_file(self, tmp_path, monkeypatch):
        import importlib

        env = tmp_path / ".env"
        env.write_text("PRICE_PROVIDERS=yahoo\n", encoding="utf-8")
        monkeypatch.delenv("PRICE_PROVIDERS", raising=False)
        self._reload(monkeypatch, env)
        from app.providers import prices

        importlib.reload(prices)
        assert prices.order() == ["yahoo"]

    def test_the_env_file_is_never_committed(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "\n.env\n" in gitignore, "El .env con datos personales debe estar ignorado."
        assert (REPO_ROOT / ".env.example").exists(), "Debe haber un ejemplo versionado."

    def test_report_says_where_each_setting_comes_from(self, tmp_path, monkeypatch):
        """Perseguir un ajuste que no se aplica es frustrante; la herramienta
        debe decir de que archivo sale cada valor."""
        env = tmp_path / ".env"
        env.write_text("PRICE_PROVIDERS=yahoo\n", encoding="utf-8")
        monkeypatch.delenv("INVEST_CONTACT", raising=False)
        monkeypatch.delenv("PRICE_PROVIDERS", raising=False)
        cfg = self._reload(monkeypatch, env)

        por_nombre = {i["name"]: i for i in cfg.config_report()}
        assert por_nombre["PRICE_PROVIDERS"]["origin"] == ".env"
        assert por_nombre["INVEST_CONTACT"]["origin"] == "por defecto"

        monkeypatch.setenv("INVEST_CONTACT", "yo@ejemplo.pe")
        cfg = self._reload(monkeypatch, env)
        por_nombre = {i["name"]: i for i in cfg.config_report()}
        assert por_nombre["INVEST_CONTACT"]["origin"] == "variable de entorno"

    def test_the_finnhub_key_value_is_never_printed(self, tmp_path, monkeypatch):
        """Un secreto no se muestra en un informe que la gente pega en chats."""
        env = tmp_path / ".env"
        env.write_text("FINNHUB_API_KEY=d9s9pc1r01qopv46bk40\n", encoding="utf-8")
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        cfg = self._reload(monkeypatch, env)

        entrada = next(i for i in cfg.config_report() if i["name"] == "FINNHUB_API_KEY")
        assert "d9s9pc1r01qopv46bk40" not in entrada["value"]
        assert "puesta" in entrada["value"]
        texto_completo = " ".join(f"{i['name']}{i['value']}{i['origin']}" for i in cfg.config_report())
        assert "d9s9pc1r01qopv46bk40" not in texto_completo

    def test_a_bom_written_by_windows_powershell_is_tolerated(self, tmp_path, monkeypatch):
        """Regresion de un fallo real en Windows.

        "Set-Content -Encoding UTF8" en PowerShell 5.1 antepone un BOM. Ese BOM
        se pega a la PRIMERA clave del archivo, que deja de reconocerse mientras
        las demas funcionan: el sintoma es que un solo ajuste se ignora en
        silencio, que es dificilisimo de diagnosticar.
        """
        env = tmp_path / ".env"
        env.write_bytes(
            "﻿INVEST_CONTACT=yo@ejemplo.pe\nPRICE_PROVIDERS=yahoo\n".encode("utf-8")
        )
        monkeypatch.delenv("INVEST_CONTACT", raising=False)
        cfg = self._reload(monkeypatch, env)
        assert cfg.CONTACT_EMAIL == "yo@ejemplo.pe", "El BOM se comio la primera clave."
        assert "INVEST_CONTACT" in cfg._FILE_VALUES

    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "latin-1"])
    def test_other_windows_encodings_are_read(self, tmp_path, monkeypatch, encoding):
        """El Bloc de notas ofrece varias codificaciones y el usuario no tiene por
        que saber cual elegir. Ninguna debe impedir arrancar: un .env en UTF-16
        llegaba a reventar el arranque entero con UnicodeDecodeError."""
        env = tmp_path / f".env-{encoding}"
        env.write_bytes("INVEST_CONTACT=yo@ejemplo.pe\n".encode(encoding))
        monkeypatch.delenv("INVEST_CONTACT", raising=False)
        cfg = self._reload(monkeypatch, env)
        assert cfg.CONTACT_EMAIL == "yo@ejemplo.pe"

    def test_binary_garbage_does_not_crash_startup(self, tmp_path, monkeypatch):
        """Un .env corrupto degrada a los valores por defecto, no tumba la app."""
        env = tmp_path / ".env"
        env.write_bytes(b"\x00\xff\xfe\x01binario sin sentido\x00")
        monkeypatch.delenv("INVEST_CONTACT", raising=False)
        cfg = self._reload(monkeypatch, env)
        assert cfg.CONTACT_EMAIL.endswith("example.com")


class TestHouseIndexConnector:
    """El indice oficial de la Camara: presentaciones, no transacciones.

    Es importante que esto no invente tickers. Sin ticker el dato vale poco,
    pero un ticker inventado valdria mucho menos que nada.
    """

    def _zip_with(self, xml: bytes) -> bytes:
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("2026FD.xml", xml)
        return buf.getvalue()

    INDEX = b"""<?xml version="1.0"?>
    <FinancialDisclosure>
      <Member><Last>Perez</Last><First>Maria</First><FilingType>P</FilingType>
        <StateDst>CA12</StateDst><Year>2026</Year><FilingDate>3/14/2026</FilingDate>
        <DocID>20026001</DocID></Member>
      <Member><Last>Smith</Last><First>John</First><FilingType>O</FilingType>
        <StateDst>TX07</StateDst><Year>2026</Year><FilingDate>5/15/2026</FilingDate>
        <DocID>20026002</DocID></Member>
    </FinancialDisclosure>"""

    def _connector(self):
        import sys

        sys.path.insert(0, str(REPO_ROOT))
        from connectors.house import HouseConnector

        return HouseConnector()

    def test_only_periodic_transaction_reports_are_kept(self):
        """Un informe anual no dice nada sobre operaciones concretas."""
        res = self._connector().parse_index(self._zip_with(self.INDEX), 2026)
        assert len(res) == 1
        assert res[0].filer_name == "Maria Perez"

    def test_it_never_invents_a_ticker(self):
        res = self._connector().parse_index(self._zip_with(self.INDEX), 2026)
        assert res[0].ticker == ""
        assert "no trae" in res[0].asset_description.lower() or "PDF" in res[0].asset_description

    def test_it_links_the_pdf_where_the_detail_lives(self):
        res = self._connector().parse_index(self._zip_with(self.INDEX), 2026)
        assert res[0].extra["pdf_url"].endswith("/2026/20026001.pdf")

    def test_the_transaction_format_still_parses(self):
        """El formato con transacciones (el del self-test) no puede romperse."""
        sample = (REPO_ROOT / "samples" / "sample_FD.xml").read_bytes()
        res = self._connector().parse(sample)
        assert {d.ticker for d in res} >= {"AAPL", "MSFT"}

    def test_a_corrupt_download_explains_itself(self):
        import pytest as _pytest

        with _pytest.raises(ValueError) as err:
            self._connector().parse_index(b"esto no es un zip", 2026)
        assert "ZIP" in str(err.value)

    def test_tickerless_rows_never_reach_the_investment_tool(self):
        """El proveedor de contexto busca por ticker, asi que las filas sin
        ticker no pueden contaminar ninguna recomendacion."""
        from app.providers import stockact

        assert stockact.fetch_signal("") is None
