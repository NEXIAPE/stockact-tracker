"""Iniciar y cerrar sesión. Es la única puerta cuando la app está publicada."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, Field

from .. import auth
from ..db import get_conn

router = APIRouter(prefix="/api/auth", tags=["acceso"])


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=512)


@router.get("/status")
def status(sesion: Optional[str] = Cookie(default=None)):
    """¿Hace falta contraseña, y tengo sesión abierta?

    Es pública a propósito: el frontend necesita saber si pintar el formulario
    de acceso o la aplicación. No revela nada que sirva a un atacante.
    """
    protegida = auth.auth_required()
    if not protegida:
        return {
            "auth_required": False,
            "authenticated": True,
            "notice": (
                "Sin contraseña configurada. Correcto en tu máquina; si publicas esto en "
                "internet, cualquiera con la dirección vería y podría borrar tus datos."
            ),
        }

    with get_conn() as conn:
        activa = auth.session_is_valid(conn, sesion or "")
    return {"auth_required": True, "authenticated": activa, "notice": ""}


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response):
    """Comprueba la contraseña y abre sesión.

    El mensaje de error es el mismo siempre: cualquier diferencia entre "no hay
    contraseña puesta" y "la contraseña es incorrecta" es información gratis
    para quien esté probando.
    """
    if not auth.auth_required():
        return {
            "ok": True,
            "auth_required": False,
            "message": "Esta instancia no tiene contraseña configurada.",
        }

    clave = auth.client_key(request)
    auth.check_not_locked(clave)

    if not auth.verify_password(payload.password, auth.configured_hash()):
        auth.record_failure(clave)
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail={"error": "credenciales_invalidas", "message": "Contraseña incorrecta."},
        )

    auth.record_success(clave)
    with get_conn() as conn:
        token, expira = auth.create_session(
            conn, user_agent=request.headers.get("user-agent", "")
        )
    auth.set_session_cookie(response, token, expira)
    return {"ok": True, "expires_at": expira.isoformat()}


@router.post("/logout")
def logout(response: Response, sesion: Optional[str] = Cookie(default=None)):
    """Cierra esta sesión. El token queda invalidado al instante, no caducado."""
    with get_conn() as conn:
        auth.destroy_session(conn, sesion or "")
    auth.clear_session_cookie(response)
    return {"ok": True}


@router.post("/logout-all", dependencies=[Depends(auth.require_session)])
def logout_all(response: Response):
    """Cierra TODAS las sesiones abiertas, estén donde estén.

    Para cuando sospechas que alguien más pudo entrar, o pierdes un dispositivo.

    EXIGE SESIÓN. Sin esa comprobación, un desconocido podía invalidar todas tus
    sesiones sin autenticarse: no vería tus datos, pero te echaría de la
    aplicación cuantas veces quisiera. Cerrar sesiones es cambiar el estado de
    seguridad, y eso nunca puede hacerse desde fuera.
    """
    with get_conn() as conn:
        cerradas = auth.destroy_all_sessions(conn)
    auth.clear_session_cookie(response)
    return {"ok": True, "closed": cerradas}
