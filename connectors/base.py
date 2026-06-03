"""Interfaz base de un conector modular."""

from __future__ import annotations

from typing import List

from models import Disclosure
from httpclient import HttpClient


class Connector:
    """Clase base. Subclasea y mapea la fuente al formato ``Disclosure``.

    Atributos de clase:
      name     -- identificador corto de la fuente ("house", "senate", ...)
      enabled  -- si False, el orquestador lo ignora (esqueleto desactivado)
    """

    name: str = "base"
    enabled: bool = False

    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()

    def fetch(self) -> List[Disclosure]:
        """Obtiene divulgaciones en vivo desde la fuente.

        Debe devolver una lista de ``Disclosure``. Implementación obligatoria
        en cada conector activo.
        """
        raise NotImplementedError

    def parse(self, raw: bytes) -> List[Disclosure]:
        """Parsea un payload crudo (bytes) al formato común.

        Separar fetch/parse permite probar el parseo offline con samples.
        """
        raise NotImplementedError
