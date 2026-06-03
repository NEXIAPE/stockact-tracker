"""Conectores modulares para fuentes de divulgaciones STOCK Act.

Cada conector traduce el formato propio de su fuente al formato común
``Disclosure``. La v1 trae la Cámara (House) ACTIVA; el Senado y un agregador
externo vienen como ESQUELETOS DESACTIVADOS, con instrucciones para activarlos.
"""

from .base import Connector
from .house import HouseConnector
from .senate import SenateConnector
from .aggregator import AggregatorConnector

# Sólo los conectores con ``enabled = True`` se ejecutan. Para activar Senado o
# el agregador, pon su flag ``enabled`` en True (ver cada archivo).
ALL_CONNECTORS = [
    HouseConnector,
    SenateConnector,
    AggregatorConnector,
]


def active_connectors():
    """Devuelve instancias de los conectores actualmente activados."""
    return [cls() for cls in ALL_CONNECTORS if cls.enabled]
