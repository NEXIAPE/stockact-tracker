"""
API de la herramienta de inversión personal.

SOLO LECTURA. No existe en todo este backend ninguna ruta, cliente ni
credencial que pueda enviar una orden a un bróker. El cliente HTTP sólo hace
GET contra fuentes de datos públicas. Tú decides y tú ejecutas a mano en tu
bróker; la herramienta te ayuda a decidir y guarda lo que le cuentas.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from .config import ALLOWED_ORIGINS, FINNHUB_ENABLED
from .core.guards import NOT_ADVICE_NOTICE, READ_ONLY_NOTICE, HardRuleViolation
from .db import init_db
from .routers import analysis, briefing, data, portfolio, profile, watchlist

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Herramienta de inversión personal",
    version="1.0.0",
    description=(
        "Edición personal de un solo usuario. Sugiere ideas de compra/venta/mantener con "
        "sus razones, sus riesgos y su contra-argumento. NUNCA ejecuta órdenes: es de solo "
        "lectura. No es asesoría financiera ni tributaria."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(HardRuleViolation)
def _hard_rule_handler(request: Request, exc: HardRuleViolation) -> JSONResponse:
    """Una regla dura incumplida bloquea la respuesta. Nunca se degrada en silencio."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "regla_dura_incumplida",
            "rule": exc.rule,
            "message": exc.detail,
            "explanation": (
                "La herramienta bloqueó su propia respuesta porque incumplía una de sus "
                "reglas innegociables (todo número citado, toda recomendación con riesgos "
                "y contra-caso, ningún lenguaje de urgencia)."
            ),
        },
    )


app.include_router(profile.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(analysis.router)
app.include_router(briefing.router)
app.include_router(data.router)


@app.get("/api/health", tags=["estado"])
def health():
    return {
        "ok": True,
        "read_only": True,
        "broker_connection": None,
        "finnhub_configured": FINNHUB_ENABLED,
        "notices": {"read_only": READ_ONLY_NOTICE, "not_advice": NOT_ADVICE_NOTICE},
    }
