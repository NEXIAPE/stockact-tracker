"""
Guardianes de las REGLAS DURAS del producto.

Estas reglas no son convenciones ni buenas intenciones: son validaciones que
BLOQUEAN la respuesta. Si una recomendación las incumple, la herramienta
devuelve un error en vez de mostrar algo defectuoso. Preferimos no mostrar
nada antes que mostrar algo que te empuje a una mala decisión.

Reglas implementadas aquí:

  1. ANTI-INVENCIÓN   Ninguna cifra en la prosa puede existir si no procede de
                      un ``DataPoint`` citado que acompañe a la recomendación.
  2. COMPLETITUD      Ninguna recomendación se emite sin al menos un riesgo
                      concreto y sin su contra-argumento.
  3. ANTI-FOMO        Ningún texto puede usar lenguaje de urgencia, presión o
                      miedo a quedarse fuera.
  4. SÓLO LECTURA     Ninguna ruta de código puede enviar órdenes a un bróker.
                      (Se verifica además con un test que escanea el repo.)
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from .datapoint import DataPoint, Datum


class HardRuleViolation(Exception):
    """Se incumplió una regla dura. La respuesta debe bloquearse."""

    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"[{rule}] {detail}")


# ---------------------------------------------------------------------------
# 1. ANTI-INVENCIÓN DE NÚMEROS
# ---------------------------------------------------------------------------

# Cualquier grupo de dígitos, con separadores de miles/decimales.
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")

# Cifras que forman parte del NOMBRE de un concepto, no de un dato: "media de
# 200 días", "máximo de 52 semanas", "S&P 500". No afirman nada sobre el activo,
# así que no requieren cita. La lista es corta y cerrada a propósito: cualquier
# otra cifra en prosa tiene que venir de un dato con fuente y fecha.
_ALWAYS_ALLOWED: set[str] = {
    "50",    # media móvil de 50 días
    "200",   # media móvil de 200 días
    "52",    # máximo/mínimo de 52 semanas
    "12",    # "últimos 12 meses"
    "500",   # S&P 500
    "10",    # formulario 10-K
}


def collect_allowed_numbers(data: Iterable[Datum]) -> set[str]:
    """Conjunto de cifras que SÍ pueden aparecer en prosa, por estar citadas."""
    allowed = set(_ALWAYS_ALLOWED)
    for d in data:
        if isinstance(d, DataPoint):
            allowed |= d.numeric_tokens()
    return allowed


def assert_numbers_are_cited(text: str, allowed: set[str], where: str) -> None:
    """Falla si la prosa contiene una cifra que no procede de un dato citado.

    La convención del motor es escribir la narrativa SIN cifras y dejar los
    números en el bloque de evidencia (donde cada uno lleva su fuente y fecha).
    Este guardián existe para que una plantilla nueva no pueda saltarse eso
    por descuido.
    """
    for match in _NUMBER_RE.finditer(text or ""):
        token = match.group(0)
        normalized = {token, token.replace(",", ""), token.replace(".", "")}
        if normalized & allowed:
            continue
        raise HardRuleViolation(
            "ANTI-INVENCION",
            f"En «{where}» aparece la cifra '{token}' sin un dato citado que la "
            f"respalde. Todo número debe venir de una fuente real con fecha.",
        )


# ---------------------------------------------------------------------------
# 2. COMPLETITUD DE LA RECOMENDACIÓN
# ---------------------------------------------------------------------------

MIN_COUNTERARGUMENT_CHARS = 40


def assert_recommendation_complete(
    *,
    thesis: str,
    risks: Sequence[str],
    counter_argument: str,
    confidence_basis: Sequence[str],
    portfolio_fit: str,
) -> None:
    """Una recomendación sin riesgos ni contra-caso es un DEFECTO. Se bloquea."""
    if not (thesis or "").strip():
        raise HardRuleViolation("COMPLETITUD", "La recomendación no tiene tesis.")

    concrete_risks = [r for r in risks if (r or "").strip()]
    if not concrete_risks:
        raise HardRuleViolation(
            "COMPLETITUD",
            "La recomendación no lista ningún riesgo concreto. No se puede mostrar.",
        )

    if len((counter_argument or "").strip()) < MIN_COUNTERARGUMENT_CHARS:
        raise HardRuleViolation(
            "COMPLETITUD",
            "Falta el contra-argumento (por qué esta idea podría estar equivocada). "
            "No se puede mostrar una recomendación sin su contra-caso.",
        )

    if not [b for b in confidence_basis if (b or "").strip()]:
        raise HardRuleViolation(
            "COMPLETITUD",
            "El nivel de confianza no declara en qué se basa.",
        )

    if not (portfolio_fit or "").strip():
        raise HardRuleViolation(
            "COMPLETITUD",
            "Falta el encaje con tu cartera y tu estrategia.",
        )


# ---------------------------------------------------------------------------
# 3. ANTI-FOMO / ANTI-URGENCIA
# ---------------------------------------------------------------------------

_FOMO_PATTERNS = [
    r"\bcompra ya\b",
    r"\bvende ya\b",
    r"\bahora o nunca\b",
    r"\bno te lo pierdas\b",
    r"\búltima oportunidad\b",
    r"\bultima oportunidad\b",
    r"\boportunidad única\b",
    r"\boportunidad unica\b",
    r"\burgente\b",
    r"\bcorre\b",
    r"\bdate prisa\b",
    r"\bantes de que\s+(suba|sea tarde)\b",
    r"\bimperdible\b",
    r"\bgarantizad[oa]s?\b",
    r"\bseguro que\s+(sube|baja)\b",
    r"\bdinero fácil\b",
    r"\bdinero facil\b",
    r"\bse dispara\b",
    r"\bexplota\b",
    r"\bal alza sin freno\b",
    r"\bmultiplicar[áa]\b",
    r"!{1,}",
]

_FOMO_RE = re.compile("|".join(_FOMO_PATTERNS), re.IGNORECASE)


def assert_no_pressure_language(text: str, where: str) -> None:
    """Las alertas e ideas se enmarcan como «vale la pena mirar», nunca como
    urgencia. Empujar a operar de más es un defecto del producto."""
    match = _FOMO_RE.search(text or "")
    if match:
        raise HardRuleViolation(
            "ANTI-FOMO",
            f"En «{where}» hay lenguaje de urgencia o presión: '{match.group(0).strip()}'. "
            f"La herramienta sugiere y explica; no mete prisa.",
        )


# ---------------------------------------------------------------------------
# 4. SÓLO LECTURA — NUNCA EJECUTA
# ---------------------------------------------------------------------------

# Señales de que alguien intentó cablear ejecución de órdenes. El test
# ``tests/test_no_broker.py`` escanea el repositorio buscando estos términos.
BROKER_EXECUTION_MARKERS = [
    "place_order",
    "submit_order",
    "create_order",
    "send_order",
    "execute_trade",
    "place_trade",
    "buy_shares",
    "sell_shares",
    "alpaca",
    "hapi.trade",
    "hapitrade",
    "interactivebrokers",
    "ib_insync",
    "tda-api",
    "tradier",
    "robinhood",
    "ccxt",
]

READ_ONLY_NOTICE = (
    "Esta herramienta es de SOLO LECTURA: sugiere y explica, nunca envía órdenes "
    "ni se conecta a tu bróker para operar. Cualquier operación la ejecutas tú, "
    "a mano, en hAPI."
)

NOT_ADVICE_NOTICE = (
    "Esto no es asesoría financiera profesional ni tributaria. Invertir desde Perú "
    "en un bróker extranjero tiene implicancias tributarias (renta de fuente "
    "extranjera, y posible retención en EE. UU. sobre dividendos): consúltalas con "
    "un contador."
)
