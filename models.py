"""
Formato común de datos para el rastreador STOCK Act.

Todos los conectores (Cámara, Senado, agregador externo) deben emitir objetos
``Disclosure`` para que las capas superiores (consolidación, persistencia,
informe) trabajen con un único esquema, sin importar la fuente.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional
import hashlib


# Tipos de transacción normalizados.
PURCHASE = "purchase"
SALE = "sale"
EXCHANGE = "exchange"
UNKNOWN = "unknown"


@dataclass
class Disclosure:
    """Una divulgación de transacción individual (STOCK Act / PTR).

    Es el "formato común" que comparten todos los conectores. Un conector es
    responsable de mapear su esquema propio a estos campos.
    """

    # --- Identidad / procedencia -------------------------------------------
    source: str                      # "house", "senate", "aggregator", ...
    doc_id: str                      # ID del documento/filing en la fuente
    filer_name: str                  # Nombre del legislador que presenta

    # --- Detalle de la transacción -----------------------------------------
    ticker: str                      # Símbolo bursátil (normalizado a mayúsc.)
    asset_description: str           # Descripción del activo
    transaction_type: str            # PURCHASE / SALE / EXCHANGE / UNKNOWN
    transaction_date: Optional[date] # Fecha de la operación
    notification_date: Optional[date]  # Fecha de notificación/presentación

    # Rango de monto, tal como lo publica la fuente (montos exactos no se
    # divulgan en el STOCK Act; sólo bandas).
    amount_range: str = ""
    amount_low: float = 0.0
    amount_high: float = 0.0

    # --- Enmiendas ----------------------------------------------------------
    is_amendment: bool = False
    amends_doc_id: Optional[str] = None  # doc_id del filing original enmendado

    # --- Clasificación ------------------------------------------------------
    sector: str = "Unknown"

    # --- Metadatos crudos opcionales ---------------------------------------
    extra: dict = field(default_factory=dict)

    def transaction_key(self) -> str:
        """Clave de negocio para deduplicación EXACTA.

        Dos divulgaciones con la misma clave describen la misma operación
        económica (mismo legislador, ticker, tipo, fecha y monto). El
        ``doc_id`` se excluye a propósito: la misma operación puede aparecer
        en filings distintos.
        """
        parts = [
            self.source,
            _norm(self.filer_name),
            _norm(self.ticker),
            self.transaction_type,
            str(self.transaction_date or ""),
            self.amount_range.strip().lower(),
        ]
        raw = "|".join(parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def amendment_subject_key(self) -> str:
        """Clave que identifica al *legislador + activo* que una enmienda
        corrige. Se usa para fusionar enmiendas contra el original cuando la
        enmienda no apunta a una transacción concreta sino a un filing.
        """
        parts = [self.source, _norm(self.filer_name), _norm(self.ticker)]
        return "|".join(parts)

    def to_row(self) -> dict:
        d = asdict(self)
        d["transaction_date"] = str(self.transaction_date or "")
        d["notification_date"] = str(self.notification_date or "")
        d.pop("extra", None)
        return d


def _norm(value: str) -> str:
    return (value or "").strip().lower()
