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

import io
import zipfile
from typing import List, Optional
import xml.etree.ElementTree as ET
from datetime import date, datetime

from connectors.base import Connector
from models import Disclosure, PURCHASE, SALE, EXCHANGE, UNKNOWN
from sectors import lookup_sector


# Índice oficial (referencia). El formato real requiere descargar el ZIP anual
# y parsear el XML índice + los PTR. Déjalo documentado para activarlo de verdad.
HOUSE_DISCLOSURE_INDEX = (
    "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP"
)

# El PDF de cada Periodic Transaction Report, que es donde estan los tickers.
HOUSE_PTR_PDF = (
    "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
)

# LIMITACION IMPORTANTE Y HONESTA
# -------------------------------
# El ZIP anual del Clerk contiene el INDICE de presentaciones: quien presento,
# de que tipo y cuando. NO contiene las transacciones. El detalle (que ticker,
# que importe, que dia) vive en el PDF de cada PTR, y esos PDFs son con mucha
# frecuencia escaneos, no texto.
#
# Es decir: la fuente oficial gratuita te dice QUIEN movio algo y CUANDO lo
# declaro, pero no QUE compro. Para eso hace falta procesar los PDFs o usar un
# agregador de terceros (ver connectors/aggregator.py, y revisa sus terminos de
# uso antes de activarlo).
INDEX_ONLY_NOTICE = (
    "El indice oficial de la Camara lista presentaciones, no transacciones. "
    "El ticker y el importe estan en el PDF de cada PTR y esta herramienta no "
    "los extrae: se guarda el enlace para que lo abras tu."
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

    def fetch(self, year: Optional[int] = None) -> List[Disclosure]:
        """Descarga el indice anual del Clerk y lo parsea.

        Devuelve una entrada por PRESENTACION, con el enlace a su PDF. Lee la
        nota INDEX_ONLY_NOTICE de arriba: el ticker no viene en el indice.
        """
        year = year or date.today().year
        url = HOUSE_DISCLOSURE_INDEX.format(year=year)
        raw = self.http.get(url)
        return self.parse_index(raw, year)

    def parse_index(self, zip_bytes: bytes, year: int) -> List[Disclosure]:
        """Extrae el XML del ZIP anual y lo convierte al formato comun."""
        try:
            archivo = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            raise ValueError(
                f"Lo que devolvio el Clerk para {year} no es un ZIP valido. "
                f"Puede que ese anio todavia no este publicado."
            ) from exc

        with archivo:
            nombres = [n for n in archivo.namelist() if n.lower().endswith(".xml")]
            if not nombres:
                raise ValueError(f"El ZIP de {year} no contiene ningun XML.")
            contenido = archivo.read(nombres[0])

        return self.parse(contenido)

    def parse(self, raw: bytes) -> List[Disclosure]:
        """Parsea un XML de la Camara al formato comun.

        Acepta los DOS formatos que existen, porque son distintos:
          * ``Filing`` con ``Transactions`` -> detalle de operaciones (el que
            usa samples/sample_FD.xml y el --self-test).
          * ``Member`` -> el indice anual real que publica el Clerk, que no
            trae transacciones.
        """
        root = ET.fromstring(raw)

        if root.find("Filing") is None and root.find("Member") is not None:
            return self._parse_members(root)

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


    def _parse_members(self, root) -> List[Disclosure]:
        """Indice anual: una entrada por presentacion, SIN transacciones.

        Solo se conservan los Periodic Transaction Reports (FilingType "P"),
        que son los que declaran compras y ventas. Los informes anuales y las
        extensiones no dicen nada sobre operaciones concretas.
        """
        disclosures: List[Disclosure] = []

        for member in root.findall("Member"):
            filing_type = _text(member, "FilingType").strip().upper()
            if filing_type != "P":
                continue

            doc_id = _text(member, "DocID")
            year_text = _text(member, "Year")
            nombre = " ".join(x for x in (
                _text(member, "Prefix"), _text(member, "First"),
                _text(member, "Last"), _text(member, "Suffix"),
            ) if x).strip()

            try:
                year = int(year_text)
            except ValueError:
                year = date.today().year

            disclosures.append(
                Disclosure(
                    source=self.name,
                    doc_id=doc_id,
                    filer_name=nombre,
                    # Sin ticker A PROPOSITO: el indice no lo trae y poner uno
                    # inventado seria mucho peor que dejarlo vacio.
                    ticker="",
                    asset_description=INDEX_ONLY_NOTICE,
                    transaction_type=UNKNOWN,
                    transaction_date=None,
                    notification_date=_parse_date(_text(member, "FilingDate")),
                    amount_range="",
                    is_amendment=False,
                    sector="Unknown",
                    extra={
                        "state_district": _text(member, "StateDst"),
                        "filing_type": filing_type,
                        "pdf_url": HOUSE_PTR_PDF.format(year=year, doc_id=doc_id) if doc_id else "",
                        "note": INDEX_ONLY_NOTICE,
                    },
                )
            )
        return disclosures


def _text(node, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()
