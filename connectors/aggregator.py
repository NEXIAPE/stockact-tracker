"""
Conector de agregador externo — ESQUELETO DESACTIVADO.

Existen agregadores de terceros que recopilan operaciones del Congreso y las
exponen vía API o descargas (algunos comerciales, otros con su propia licencia
y términos de uso). Este conector es un punto de extensión genérico.

CÓMO ACTIVARLO
--------------
1. Revisa los TÉRMINOS DE USO y la licencia del agregador que elijas. Muchos
   prohíben el scraping o exigen API key / atribución. Cúmplelos.
2. Pon ``enabled = True`` más abajo.
3. Configura ``API_BASE`` y, si aplica, una API key (mejor por variable de
   entorno, no hardcodeada).
4. Implementa ``fetch`` usando ``self.http`` (User-Agent + rate limiting) y
   mapea la respuesta a ``Disclosure`` con ``source = "aggregator"``.

ADVERTENCIA: un agregador puede solapar datos con la Cámara/Senado. La capa de
consolidación deduplica por clave de negocio, pero revisa que los nombres y
tickers se normalicen igual para que el dedup funcione entre fuentes.

Mientras ``enabled = False``, el orquestador lo ignora por completo.
"""

from __future__ import annotations

from typing import List

from connectors.base import Connector
from models import Disclosure


# Configura el endpoint del agregador que vayas a usar.
API_BASE = "https://example-aggregator.invalid/api/v1/congress-trades"


class AggregatorConnector(Connector):
    name = "aggregator"
    enabled = False  # <-- DESACTIVADO. Cambia a True para activarlo.

    def fetch(self) -> List[Disclosure]:
        raise NotImplementedError(
            "Conector de agregador desactivado. Revisa términos de uso/licencia, "
            "pon enabled=True e implementa fetch() (ver encabezado del archivo)."
        )

    def parse(self, raw: bytes) -> List[Disclosure]:
        raise NotImplementedError(
            "Implementa el parseo de la respuesta del agregador aquí."
        )
