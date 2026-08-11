"""
Noticias por ticker vía RSS (gratis, sin API key).

Dos feeds, ambos públicos:

  * Yahoo Finance — titulares de prensa financiera sobre el símbolo.
  * SEC EDGAR (Atom) — presentaciones oficiales de la empresa (10-K, 8-K...).
    Esto no es "prensa": es la empresa comunicando hechos a la SEC. Se marca
    aparte porque su fiabilidad es distinta.

REGLA DEL PRODUCTO: una noticia se etiqueta siempre como INTERPRETACIÓN, nunca
como hecho, y se muestra con su fuente y su fecha. La herramienta no resume la
noticia "por su cuenta" ni le pone un número: enlaza el titular y te deja
juzgar.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

from ..config import CACHE_TTL
from .http import FetchError, client

YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
EDGAR_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"
    "&type=&dateb=&owner=include&count=20&output=atom"
)

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published: Optional[date]
    source_name: str
    kind: str          # "prensa" | "presentacion_oficial"
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "published": self.published.isoformat() if self.published else None,
            "source_name": self.source_name,
            "kind": self.kind,
            "summary": self.summary,
            # Etiqueta obligatoria: una noticia es interpretación, no un hecho
            # sobre el valor del activo.
            "interpretation_notice": (
                "Titular de terceros. Es INTERPRETACIÓN del mercado, no un hecho "
                "sobre el valor del activo."
            )
            if kind_is_press(self.kind)
            else (
                "Presentación oficial ante la SEC. Es un documento de la empresa; "
                "su lectura sigue siendo interpretación."
            ),
        }


def kind_is_press(kind: str) -> bool:
    return kind == "prensa"


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).date()
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def fetch_yahoo(ticker: str, limit: int = 12) -> List[NewsItem]:
    try:
        raw = client().get(YAHOO_RSS.format(ticker=ticker.upper()), ttl=CACHE_TTL["news"])
        root = ET.fromstring(raw)
    except (FetchError, ET.ParseError):
        return []

    items: List[NewsItem] = []
    for node in root.iter("item"):
        title = _clean(_text(node, "title"))
        link = _text(node, "link")
        if not title or not link:
            continue
        items.append(
            NewsItem(
                title=title,
                url=link,
                published=_parse_date(_text(node, "pubDate")),
                source_name="Yahoo Finance (RSS)",
                kind="prensa",
                summary=_clean(_text(node, "description"))[:280],
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_sec_filings(cik: Optional[int], limit: int = 8) -> List[NewsItem]:
    if not cik:
        return []
    try:
        raw = client().get(EDGAR_ATOM.format(cik=cik), ttl=CACHE_TTL["news"])
        root = ET.fromstring(raw)
    except (FetchError, ET.ParseError):
        return []

    ns = {"a": "http://www.w3.org/2005/Atom"}
    items: List[NewsItem] = []
    for entry in root.findall(".//a:entry", ns):
        title = _clean(_findtext(entry, "a:title", ns))
        link_node = entry.find("a:link", ns)
        link = link_node.get("href") if link_node is not None else ""
        if not title or not link:
            continue
        items.append(
            NewsItem(
                title=title,
                url=link,
                published=_parse_date(_findtext(entry, "a:updated", ns)),
                source_name="SEC EDGAR (presentaciones)",
                kind="presentacion_oficial",
                summary="",
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_news(ticker: str, cik: Optional[int] = None, limit: int = 12) -> List[NewsItem]:
    """Titulares de prensa + presentaciones oficiales, ordenados por fecha."""
    items = fetch_yahoo(ticker, limit=limit) + fetch_sec_filings(cik, limit=6)
    items.sort(key=lambda i: (i.published or date.min), reverse=True)
    return items[:limit]


def _text(node, tag: str) -> str:
    child = node.find(tag)
    return (child.text or "") if child is not None else ""


def _findtext(node, path: str, ns: dict) -> str:
    child = node.find(path, ns)
    return (child.text or "") if child is not None else ""
