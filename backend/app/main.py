"""
API de la herramienta de inversión personal.

SOLO LECTURA. No existe en todo este backend ninguna ruta, cliente ni
credencial que pueda enviar una orden a un bróker. El cliente HTTP sólo hace
GET contra fuentes de datos públicas. Tú decides y tú ejecutas a mano en tu
bróker; la herramienta te ayuda a decidir y guarda lo que le cuentas.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from . import auth
from .config import ALLOWED_ORIGINS, FINNHUB_ENABLED
from .core.guards import NOT_ADVICE_NOTICE, READ_ONLY_NOTICE, HardRuleViolation
from .db import init_db
from .routers import analysis, auth as auth_router, briefing, data, portfolio, profile, watchlist

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


# TODAS las rutas de datos van detrás de la sesión. Se aplica en el include, no
# ruta por ruta: una ruta nueva queda protegida por omisión, y olvidarse de un
# decorador no puede abrir un agujero. Sin contraseña configurada la dependencia
# no hace nada, así que en local todo sigue igual.
protegido = [Depends(auth.require_session)]

app.include_router(auth_router.router)          # la puerta, necesariamente pública
app.include_router(profile.router, dependencies=protegido)
app.include_router(portfolio.router, dependencies=protegido)
app.include_router(watchlist.router, dependencies=protegido)
app.include_router(analysis.router, dependencies=protegido)
app.include_router(briefing.router, dependencies=protegido)
app.include_router(data.router, dependencies=protegido)


@app.get("/api/health", tags=["estado"])
def health():
    """Pública a propósito, para que un balanceador pueda comprobar el servicio.

    No revela ningún dato tuyo: sólo que el proceso está vivo y si está protegido.
    """
    return {
        "ok": True,
        "read_only": True,
        "broker_connection": None,
        "finnhub_configured": FINNHUB_ENABLED,
        "auth_required": auth.auth_required(),
        "notices": {"read_only": READ_ONLY_NOTICE, "not_advice": NOT_ADVICE_NOTICE},
    }


# --- Interfaz servida por el mismo proceso ---------------------------------
# Al publicar conviene que backend y frontend salgan del mismo origen: así la
# cookie de sesión no tiene que cruzar dominios y SameSite=Strict la protege de
# verdad. Si no hay interfaz compilada, la API funciona igual.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Cualquier ruta que no sea de la API devuelve la interfaz.

        La aplicación es de una sola página: navegar a /cartera directamente
        tiene que funcionar igual que llegar desde dentro.

        Excepción: los archivos sueltos de la raíz —el icono— se sirven tal
        cual. Devolverles el index.html no da error visible, solo un icono roto
        que cuesta relacionar con su causa. Se comprueba que el nombre no lleve
        barras ni ``..`` para que esto no sirva de paseo por el disco.
        """
        if full_path and "/" not in full_path and ".." not in full_path:
            suelto = FRONTEND_DIST / full_path
            if suelto.is_file():
                return FileResponse(suelto)
        return FileResponse(FRONTEND_DIST / "index.html")
