"""
Conector de la Cámara de Representantes (House) — ACTIVO.

La Oficina del Clerk de la Cámara publica las divulgaciones financieras (incl.
los Periodic Transaction Reports / PTR que exige el STOCK Act). En producción,
los índices anuales se distribuyen como ZIP con un XML y los PTR detallados
suelen venir en PDF.

Para que el flujo sea autocontenido y testeable offline, este conector parsea
un XML de transacciones con un esquema simplificado (ver samples/sample_FD.xml).
La función ``fetch`` queda lista para apuntar a la fuente real cuando dispongas
del parseo de su formato concreto.

NOTA LEGAL/OPERATIVA: los PTR pueden presentarse con un desfase de hasta ~45
días respecto a la operación. Lo que ves "hoy" describe el pasado.
"""

from __future__ import annotations

from typing import List
import xml.etree.ElementTree as ET
from datetime import datetime

from connectors.base import Connector
from models import Disclosure, PURCHASE, SALE, EXCHANGE, UNKNOWN
from sectors import lookup_sector


# Índice oficial (referencia). El formato real requiere descargar el ZIP anual
# y parsear el XML índice + los PTR. Déjalo documentado para activarlo de verdad.
HOUSE_DISCLOSURE_INDEX = (
    "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP"
)


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_type(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ("p", "purchase", "buy"):
        return PURCHASE
    if v in ("s", "sale", "sell", "sale (full)", "sale (partial)"):
        return SALE
    if v in ("e", "exchange"):
        return EXCHANGE
    return UNKNOWN


def _parse_amount(value: str):
    """Convierte '$1,001 - $15,000' en (low, high). Bandas STOCK Act."""
    value = (value or "").strip()
    if not value:
        return 0.0, 0.0
    nums = []
    for token in value.replace("$", " ").replace("-", " ").split():
        token = token.replace(",", "")
        try:
            nums.append(float(token))
        except ValueError:
            continue
    if not nums:
        return 0.0, 0.0
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)


class HouseConnector(Connector):
    name = "house"
    enabled = True  # <-- Cámara ACTIVA en v1

    def fetch(self) -> List[Disclosure]:
        """En producción: descargar el ZIP anual del Clerk y parsearlo.

        Aquí se deja el esqueleto de la descarga (cortés, vía HttpClient) y se
        delega el parseo a ``parse``. Para datos reales necesitarás manejar el
        ZIP y el formato concreto (XML índice + PTR).
        """
        raise NotImplementedError(
            "fetch en vivo requiere descargar y parsear el ZIP anual del Clerk "
            "de la Cámara. Usa parse(bytes) con datos reales, o el --self-test "
            "con samples/sample_FD.xml para validar el flujo offline."
        )

    def parse(self, raw: bytes) -> List[Disclosure]:
        """Parsea el XML de transacciones (esquema simplificado) a Disclosure."""
        root = ET.fromstring(raw)
        disclosures: List[Disclosure] = []

        for filing in root.findall("Filing"):
            doc_id = _text(filing, "DocID")
            member = _text(filing, "Member")
            filing_date = _parse_date(_text(filing, "FilingDate"))
            amends = _text(filing, "Amends")
            is_amendment = bool(amends)

            transactions = filing.find("Transactions")
            if transactions is None:
                continue

            for tx in transactions.findall("Transaction"):
                ticker = _text(tx, "Ticker").upper()
                amount_range = _text(tx, "Amount")
                low, high = _parse_amount(amount_range)
                disclosures.append(
                    Disclosure(
                        source=self.name,
                        doc_id=doc_id,
                        filer_name=member,
                        ticker=ticker,
                        asset_description=_text(tx, "AssetDescription"),
                        transaction_type=_parse_type(_text(tx, "Type")),
                        transaction_date=_parse_date(_text(tx, "Date")),
                        notification_date=filing_date,
                        amount_range=amount_range,
                        amount_low=low,
                        amount_high=high,
                        is_amendment=is_amendment,
                        amends_doc_id=amends or None,
                        sector=lookup_sector(ticker),
                    )
                )
        return disclosures


def _text(node, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()
