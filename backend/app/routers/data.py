"""Tus datos son tuyos: exportarlos y borrarlos. Y estado de las fuentes."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..config import CONTACT_EMAIL, DB_PATH, FINNHUB_ENABLED
from ..core.guards import NOT_ADVICE_NOTICE, READ_ONLY_NOTICE
from ..db import export_all, get_conn, wipe_all
from ..providers import stockact
from ..providers.twelvedata import enabled as _twelvedata_enabled
from ..providers.http import client

router = APIRouter(prefix="/api/data", tags=["tus datos"])


@router.get("/export")
def export(download: bool = Query(default=True)):
    """Descarga TODO lo que la herramienta sabe de ti, en JSON."""
    payload = export_all()
    headers = (
        {"Content-Disposition": 'attachment; filename="mis-datos-inversion.json"'}
        if download
        else {}
    )
    return JSONResponse(content=payload, headers=headers)


@router.delete("/wipe")
def wipe(confirm: str = Query(default="", description="Escribe BORRAR para confirmar")):
    """Borra todos tus datos. Irreversible."""
    if confirm != "BORRAR":
        return JSONResponse(
            status_code=400,
            content={
                "error": "confirmacion_requerida",
                "message": "Para borrarlo todo, repite la confirmación exacta.",
                "how": "DELETE /api/data/wipe?confirm=BORRAR",
            },
        )
    deleted = wipe_all()
    return {"ok": True, "deleted": deleted, "database": str(DB_PATH)}


@router.post("/cache/clear")
def clear_cache():
    """Vacía la caché de respuestas de las fuentes de datos (no toca tus datos)."""
    return {"ok": True, "files_removed": client().cache_clear()}


@router.get("/sources")
def sources():
    """Qué fuentes hay activas, qué dan y qué NO dan. Sin adornos."""
    return {
        "read_only_notice": READ_ONLY_NOTICE,
        "not_advice_notice": NOT_ADVICE_NOTICE,
        "contact_user_agent": CONTACT_EMAIL,
        "sources": [
            {
                "name": "Stooq",
                "provides": "Precios de cierre diario, histórico, acciones y ETFs de EE. UU.",
                "cost": "Gratis, sin clave",
                "limits": "Sólo cierre diario: no hay intradía. Sin garantía de servicio.",
                "enabled": True,
            },
            {
                "name": "SEC EDGAR (XBRL)",
                "provides": "Fundamentales oficiales de emisores de EE. UU. (10-K/20-F).",
                "cost": "Gratis, sin clave",
                "limits": (
                    "No cubre ETFs. Datos anuales: pueden ser de hace meses. Exige "
                    "User-Agent identificable y limita la tasa de peticiones."
                ),
                "enabled": True,
            },
            {
                "name": "RSS de noticias (Yahoo Finance + SEC EDGAR)",
                "provides": "Titulares por ticker y presentaciones oficiales.",
                "cost": "Gratis, sin clave",
                "limits": "Cobertura desigual. Los titulares son interpretación, no hechos.",
                "enabled": True,
            },
            {
                "name": "Twelve Data",
                "provides": "Precios de cierre diario. Tercer respaldo, por si fallan los otros dos.",
                "cost": "Plan gratuito con clave (los límites los fija Twelve Data)",
                "limits": (
                    "Requiere TWELVEDATA_API_KEY. Va el último en el orden a propósito: "
                    "su cuota diaria sólo debe gastarse si los proveedores sin clave fallan. "
                    "Hoy no resuelve ningún problema si Yahoo o Stooq te funcionan."
                ),
                "enabled": _twelvedata_enabled(),
            },
            {
                "name": "Finnhub",
                "provides": "Cotización más fresca, PER, beta, márgenes y noticias por ticker.",
                "cost": "Plan gratuito con clave (los límites los fija Finnhub)",
                "limits": (
                    "Requiere FINNHUB_API_KEY. Si se agota la cuota, la herramienta lo dice "
                    "y cae a las fuentes sin clave en lugar de inventar el dato."
                ),
                "enabled": FINNHUB_ENABLED,
            },
            {
                "name": "Rastreador STOCK Act (local, ya existía en este repo)",
                "provides": "Divulgaciones de operaciones de congresistas de EE. UU.",
                "cost": "Gratis (fuentes oficiales)",
                "limits": (
                    "Desfase legal de hasta ~45 días. Peso CERO en la recomendación: "
                    "es contexto, no señal."
                ),
                "enabled": stockact.available(),
            },
        ],
        "missing_on_purpose": [
            {
                "what": "Índice de sentimiento de mercado",
                "why": (
                    "Ninguna fuente gratuita da un sentimiento fiable. En vez de rellenar el "
                    "hueco con algo inventado, ese bloque aparece vacío y se dice por qué."
                ),
            },
            {
                "what": "Ratio de gastos y composición de los ETFs",
                "why": (
                    "No están en las fuentes gratuitas de forma fiable. Se leen en la ficha "
                    "oficial del emisor y se registran a mano, quedando citados con su fecha."
                ),
            },
        ],
    }


@router.get("/stockact")
def stockact_context(limit: int = Query(default=10, le=50)):
    """Contexto del rastreador STOCK Act. Peso cero en las recomendaciones."""
    return {
        "available": stockact.available(),
        "top_recent": stockact.top_recent(limit=limit),
        "caveat": stockact.DISCLOSURE_LAG_NOTICE,
    }
