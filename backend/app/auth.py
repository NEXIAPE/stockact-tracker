"""
Autenticación por contraseña, para poder exponer la herramienta en internet.

CONTEXTO Y RIESGO, DICHO SIN ADORNOS
------------------------------------
Esta aplicación guarda tu cartera, tu efectivo, tus tesis y tu perfil. Publicada
en internet, lo único que separa esos datos de cualquiera es esta contraseña.
En local no hacía falta nada; expuesta, esto es la única puerta.

DECISIONES Y POR QUÉ
--------------------
* **La contraseña no se guarda nunca.** Se guarda un hash PBKDF2-HMAC-SHA256 con
  sal aleatoria y 600.000 iteraciones (la recomendación de OWASP). Aunque alguien
  lea la configuración del servidor, no obtiene tu contraseña.

* **Comparación en tiempo constante** (``secrets.compare_digest``): comparar con
  ``==`` filtra información por el tiempo que tarda en fallar.

* **Sesiones en la base de datos, no cookies firmadas.** Así una sesión se puede
  REVOCAR de verdad (cerrar sesión invalida el token al instante), sobrevive a
  un reinicio y funciona con varios procesos. Una cookie firmada sólo caduca.

* **El token de sesión se guarda hasheado.** Si alguien lee la base, no puede
  suplantarte con los tokens que encuentre: es el mismo razonamiento que con la
  contraseña.

* **Cookie HttpOnly, SameSite=Strict y Secure.** HttpOnly la esconde de
  JavaScript (defensa ante XSS), SameSite frena peticiones desde otros sitios
  (defensa ante CSRF) y Secure impide que viaje por HTTP sin cifrar.

* **Límite de intentos por IP.** Sin esto, una contraseña corta cae por fuerza
  bruta en minutos.

* **Sin contraseña configurada, la aplicación NO arranca en modo público.** Es
  deliberado: un despliegue que se queda abierto por olvido es el peor fallo
  posible, y aquí es imposible que ocurra en silencio.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from fastapi import Cookie, HTTPException, Request, Response

from .config import setting

# --- Parámetros de hashing -------------------------------------------------
ALGORITHM = "sha256"
ITERATIONS = 600_000        # recomendación de OWASP para PBKDF2-HMAC-SHA256
SALT_BYTES = 16

# --- Sesión ----------------------------------------------------------------
COOKIE_NAME = "sesion"
SESSION_HOURS = 12
TOKEN_BYTES = 32            # 256 bits de entropía

# --- Límite de intentos ----------------------------------------------------
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300       # cinco minutos tras agotar los intentos

MIN_PASSWORD_LENGTH = 12


class AuthNotConfigured(RuntimeError):
    """Falta la contraseña. La aplicación se niega a quedar abierta."""


# ---------------------------------------------------------------------------
# Hashing de la contraseña
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Devuelve ``pbkdf2_sha256$iteraciones$sal$hash``, todo en hexadecimal."""
    salt = salt or secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(ALGORITHM, password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_{ALGORITHM}${ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Comprueba la contraseña en tiempo constante."""
    try:
        algo, iterations, salt_hex, expected_hex = stored.split("$")
        if not algo.startswith("pbkdf2_"):
            return False
        derived = hashlib.pbkdf2_hmac(
            algo.split("_", 1)[1],
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), expected_hex)


# Caché del hash derivado de una contraseña en claro. Derivarlo cuesta 600.000
# iteraciones a propósito, y ``configured_hash`` se consulta en CADA petición
# (la dependencia de sesión pregunta si hay contraseña). Sin esta caché, usar
# APP_PASSWORD en claro añadía ese coste a todas las peticiones de la
# aplicación, no sólo al iniciar sesión.
_derived_cache: Dict[str, str] = {}


def configured_hash() -> str:
    """El hash de la contraseña, venga de donde venga.

    Se acepta ``APP_PASSWORD`` en claro por comodidad, pero es peor: quien lea la
    configuración del servidor tendría tu contraseña, no sólo un hash inútil. El
    diagnóstico avisa cuando se está usando esa vía.
    """
    stored = setting("APP_PASSWORD_HASH").strip()
    if stored:
        return stored

    plain = setting("APP_PASSWORD").strip()
    if not plain:
        return ""
    if plain not in _derived_cache:
        _derived_cache[plain] = hash_password(plain)
    return _derived_cache[plain]


def auth_required() -> bool:
    """¿Está la aplicación en modo protegido?

    Se activa sola en cuanto hay contraseña configurada. En local, sin
    contraseña, la herramienta sigue funcionando como siempre.
    """
    return bool(configured_hash())


def password_problems(password: str) -> list:
    """Pegas de una contraseña, para avisar al configurarla."""
    problemas = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problemas.append(
            f"Tiene menos de {MIN_PASSWORD_LENGTH} caracteres. Expuesta en internet, "
            f"una contraseña corta se rompe por fuerza bruta."
        )
    if password.lower() in {"contrasena", "password", "12345678", "123456789012"}:
        problemas.append("Es una de las contraseñas más probadas que existen.")
    if password and password == password.lower() and password.isalpha():
        problemas.append("Sólo tiene letras minúsculas. Mezcla números y símbolos.")
    return problemas


# ---------------------------------------------------------------------------
# Sesiones (persistidas y revocables)
# ---------------------------------------------------------------------------
SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,   -- nunca el token en claro
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    user_agent  TEXT NOT NULL DEFAULT ''
);
"""


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn, user_agent: str = "") -> Tuple[str, datetime]:
    conn.executescript(SESSION_SCHEMA)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=SESSION_HOURS)
    conn.execute(
        "INSERT INTO sessions (token_hash, created_at, expires_at, user_agent) VALUES (?,?,?,?)",
        (_token_hash(token), now.isoformat(), expires.isoformat(), user_agent[:200]),
    )
    _purge_expired(conn, now)
    return token, expires


def session_is_valid(conn, token: str) -> bool:
    if not token:
        return False
    conn.executescript(SESSION_SCHEMA)
    row = conn.execute(
        "SELECT expires_at FROM sessions WHERE token_hash = ?", (_token_hash(token),)
    ).fetchone()
    if row is None:
        return False
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except (ValueError, TypeError):
        return False
    return datetime.now(timezone.utc) < expires


def destroy_session(conn, token: str) -> None:
    if not token:
        return
    conn.executescript(SESSION_SCHEMA)
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def destroy_all_sessions(conn) -> int:
    conn.executescript(SESSION_SCHEMA)
    cur = conn.execute("DELETE FROM sessions")
    return cur.rowcount


def _purge_expired(conn, now: datetime) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(),))


# ---------------------------------------------------------------------------
# Límite de intentos de acceso
# ---------------------------------------------------------------------------
@dataclass
class Attempts:
    count: int = 0
    locked_until: float = 0.0


_attempts: Dict[str, Attempts] = {}


def client_key(request: Request) -> str:
    """Identifica al cliente para el límite de intentos.

    Se usa la IP directa. Detrás de un proxy inverso, ``X-Forwarded-For`` la
    trae, pero esa cabecera la puede falsificar cualquiera si el proxy no la
    sanea, así que NO se usa: preferimos un límite algo más tosco a uno que se
    esquive poniendo una cabecera.
    """
    return request.client.host if request.client else "desconocido"


def check_not_locked(key: str) -> None:
    estado = _attempts.get(key)
    if estado and estado.locked_until > time.monotonic():
        restante = int(estado.locked_until - time.monotonic())
        raise HTTPException(
            status_code=429,
            detail={
                "error": "demasiados_intentos",
                "message": (
                    f"Demasiados intentos fallidos. Vuelve a probar en {restante} segundos."
                ),
                "retry_after_seconds": restante,
            },
        )


def record_failure(key: str) -> None:
    estado = _attempts.setdefault(key, Attempts())
    estado.count += 1
    if estado.count >= MAX_ATTEMPTS:
        estado.locked_until = time.monotonic() + LOCKOUT_SECONDS
        estado.count = 0


def record_success(key: str) -> None:
    _attempts.pop(key, None)


def reset_attempts() -> None:
    """Sólo para los tests."""
    _attempts.clear()


# ---------------------------------------------------------------------------
# Cookie y dependencia de FastAPI
# ---------------------------------------------------------------------------
def cookie_is_secure() -> bool:
    """En producción la cookie sólo debe viajar por HTTPS.

    Se desactiva sólo si se pide explícitamente, para poder probar en local por
    HTTP. Que el valor por defecto sea el seguro es intencionado: olvidarse de
    activarlo no puede ser lo que abra el agujero.
    """
    return setting("APP_INSECURE_COOKIE", "").strip().lower() not in ("1", "true", "si", "sí")


def set_session_cookie(response: Response, token: str, expires: datetime) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,                  # invisible para JavaScript
        secure=cookie_is_secure(),      # sólo por HTTPS
        samesite="strict",              # no se envía desde otros sitios
        max_age=SESSION_HOURS * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="strict")


def require_session(
    request: Request,
    sesion: Optional[str] = Cookie(default=None),
) -> None:
    """Dependencia que protege todas las rutas cuando hay contraseña puesta."""
    if not auth_required():
        return

    from .db import get_conn

    with get_conn() as conn:
        if not session_is_valid(conn, sesion or ""):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "no_autenticado",
                    "message": "Necesitas iniciar sesión para ver tus datos.",
                },
            )
