"""
Conector del Senado (Senate) — ESQUELETO DESACTIVADO.

El Senado publica sus divulgaciones a través del Electronic Financial
Disclosure (eFD) en https://efdsearch.senate.gov/. El portal requiere aceptar
un acuerdo (cookie de sesión) antes de consultar y devuelve resultados en
HTML/JSON paginado.

CÓMO ACTIVARLO
--------------
1. Pon ``enabled = True`` más abajo.
2. Implementa ``fetch`` para:
     a. Hacer GET a la home de eFD para aceptar el acuerdo y obtener cookies.
     b. POST al endpoint de búsqueda (data/search) con el rango de fechas.
     c. Para cada PTR, abrir el detalle y extraer las transacciones.
   Hazlo SIEMPRE a través de ``self.http`` (User-Agent + rate limiting).
3. Mapea cada transacción a ``Disclosure`` con ``source = "senate"``.
4. Respeta los términos de uso del portal y los rate limits.

Mientras ``enabled = False``, el orquestador lo ignora por completo.
"""

from __future__ import annotations

from typing import List

from connectors.base import Connector
from models import Disclosure


SENATE_EFD_HOME = "https://efdsearch.senate.gov/search/home/"
SENATE_EFD_SEARCH = "https://efdsearch.senate.gov/search/report/data/"


class SenateConnector(Connector):
    name = "senate"
    enabled = False  # <-- DESACTIVADO. Cambia a True para activarlo.

    def fetch(self) -> List[Disclosure]:
        raise NotImplementedError(
            "Conector del Senado desactivado. Pon enabled=True e implementa "
            "fetch() siguiendo las instrucciones del encabezado de este archivo."
        )

    def parse(self, raw: bytes) -> List[Disclosure]:
        raise NotImplementedError(
            "Implementa el parseo del formato eFD del Senado aquí."
        )
