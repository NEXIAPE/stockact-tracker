"""
Tests de la autenticación.

Publicada en internet, esta contraseña es lo único que separa la cartera del
usuario de cualquiera. Estos tests comprueban que no haya ninguna puerta
lateral: ni una ruta sin proteger, ni una sesión que sobreviva al cierre, ni
una contraseña guardada en claro.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth

PASSWORD = "una-contrasena-larga-y-decente-2026"
# Derivar la clave es caro a propósito (600.000 iteraciones). Se hace una sola
# vez para todo el módulo en lugar de por test.
PASSWORD_HASH = auth.hash_password(PASSWORD)


@pytest.fixture()
def protected(tmp_path, monkeypatch):
    """App con contraseña puesta, base de datos temporal y sin red."""
    db = tmp_path / "auth.db"
    monkeypatch.setattr("app.config.DB_PATH", db)
    monkeypatch.setattr("app.db.DB_PATH", db)
    # El hash se calcula UNA vez. Antes se recalculaba en cada consulta de
    # configuración —600.000 iteraciones cada vez— y la suite pasaba de tres
    # segundos a más de un minuto.
    valores = {
        "APP_PASSWORD_HASH": PASSWORD_HASH,
        "APP_INSECURE_COOKIE": "1",   # el cliente de test habla http
    }
    monkeypatch.setattr(auth, "setting", lambda name, default="": valores.get(name, default))
    auth.reset_attempts()

    from app.main import app

    with TestClient(app) as c:
        yield c
    auth.reset_attempts()


# ---------------------------------------------------------------------------
class TestPasswordHashing:
    def test_the_password_itself_is_never_stored(self):
        stored = auth.hash_password(PASSWORD)
        assert PASSWORD not in stored
        assert stored.startswith("pbkdf2_sha256$")

    def test_the_same_password_hashes_differently_every_time(self):
        """Sal aleatoria: dos hashes iguales delatarían contraseñas iguales."""
        assert auth.hash_password(PASSWORD) != auth.hash_password(PASSWORD)

    def test_verification_accepts_the_right_one_and_rejects_the_rest(self):
        stored = auth.hash_password(PASSWORD)
        assert auth.verify_password(PASSWORD, stored) is True
        assert auth.verify_password(PASSWORD + "x", stored) is False
        assert auth.verify_password("", stored) is False

    def test_a_corrupt_stored_hash_does_not_let_anyone_in(self):
        for basura in ("", "cualquier-cosa", "pbkdf2_sha256$mal", "$$$"):
            assert auth.verify_password(PASSWORD, basura) is False

    def test_the_iteration_count_meets_current_guidance(self):
        assert auth.ITERATIONS >= 600_000

    def test_weak_passwords_are_flagged(self):
        assert auth.password_problems("corta")
        assert auth.password_problems("password")
        assert auth.password_problems("solamenteletras")
        assert not auth.password_problems("Un4-Contrasena-Larga-Y-Solida!")


# ---------------------------------------------------------------------------
class TestNoBackDoors:
    """Lo que más importa: que no quede ninguna ruta abierta."""

    RUTAS_DE_DATOS = [
        "/api/profile", "/api/portfolio", "/api/portfolio/thesis",
        "/api/portfolio/performance", "/api/portfolio/trades", "/api/watchlist",
        "/api/briefing", "/api/alerts", "/api/ideas", "/api/analyze/VOO",
        "/api/data/export", "/api/data/sources", "/api/prices/VOO",
    ]

    @pytest.mark.parametrize("ruta", RUTAS_DE_DATOS)
    def test_every_data_route_needs_a_session(self, protected, ruta):
        r = protected.get(ruta)
        assert r.status_code == 401, f"{ruta} respondió sin sesión."

    def test_writing_also_needs_a_session(self, protected):
        assert protected.post("/api/profile", json={}).status_code == 401
        assert protected.put("/api/portfolio/cash", json={"amount": 1}).status_code == 401
        assert protected.request(
            "DELETE", "/api/data/wipe?confirm=BORRAR"
        ).status_code == 401

    def test_health_stays_public_but_leaks_nothing(self, protected):
        body = protected.get("/api/health").json()
        assert body["ok"] is True
        assert body["auth_required"] is True
        texto = str(body).lower()
        assert "password" not in texto and "hash" not in texto

    def test_a_made_up_cookie_does_not_work(self, protected):
        protected.cookies.set(auth.COOKIE_NAME, "token-inventado-por-un-atacante")
        assert protected.get("/api/portfolio").status_code == 401


# ---------------------------------------------------------------------------
class TestLoginFlow:
    def test_the_right_password_opens_a_session(self, protected):
        r = protected.post("/api/auth/login", json={"password": PASSWORD})
        assert r.status_code == 200
        assert protected.get("/api/profile").status_code == 200

    def test_the_wrong_password_does_not(self, protected):
        r = protected.post("/api/auth/login", json={"password": "otra-cosa"})
        assert r.status_code == 401
        assert protected.get("/api/profile").status_code == 401

    def test_the_error_never_says_which_part_was_wrong(self, protected):
        detalle = protected.post("/api/auth/login", json={"password": "x"}).json()["detail"]
        assert detalle["message"] == "Contraseña incorrecta."
        assert "hash" not in str(detalle).lower()

    def test_the_cookie_is_protected(self, protected):
        r = protected.post("/api/auth/login", json={"password": PASSWORD})
        cookie = r.headers.get("set-cookie", "").lower()
        assert "httponly" in cookie, "Sin HttpOnly, un XSS robaría la sesión."
        assert "samesite=strict" in cookie, "Sin SameSite, cabría un CSRF."

    def test_logging_out_revokes_the_token_immediately(self, protected):
        protected.post("/api/auth/login", json={"password": PASSWORD})
        token = protected.cookies.get(auth.COOKIE_NAME)
        protected.post("/api/auth/logout")
        # Aunque alguien tuviera el token robado, ya no sirve.
        protected.cookies.set(auth.COOKIE_NAME, token)
        assert protected.get("/api/portfolio").status_code == 401

    def test_logout_all_closes_every_session(self, protected):
        protected.post("/api/auth/login", json={"password": PASSWORD})
        token = protected.cookies.get(auth.COOKIE_NAME)
        protected.post("/api/auth/logout-all")
        protected.cookies.set(auth.COOKIE_NAME, token)
        assert protected.get("/api/portfolio").status_code == 401

    def test_a_stranger_cannot_close_your_sessions(self, protected):
        """Regresión de un fallo real: /logout-all no exigía sesión.

        Un desconocido no vería tus datos, pero podía invalidar tus sesiones
        cuantas veces quisiera y echarte de la aplicación. Cerrar sesiones es
        cambiar el estado de seguridad, y eso nunca puede hacerse desde fuera.
        """
        protected.post("/api/auth/login", json={"password": PASSWORD})
        mia = protected.cookies.get(auth.COOKIE_NAME)

        protected.cookies.clear()                 # el intruso no tiene cookie
        assert protected.post("/api/auth/logout-all").status_code == 401

        # Y mi sesión sigue viva: el intento no me echó.
        protected.cookies.set(auth.COOKIE_NAME, mia)
        assert protected.get("/api/portfolio").status_code == 200

    def test_status_tells_the_frontend_what_to_show(self, protected):
        assert protected.get("/api/auth/status").json() == {
            "auth_required": True, "authenticated": False, "notice": ""
        }
        protected.post("/api/auth/login", json={"password": PASSWORD})
        assert protected.get("/api/auth/status").json()["authenticated"] is True


# ---------------------------------------------------------------------------
class TestBruteForce:
    def test_repeated_failures_lock_the_door(self, protected):
        for _ in range(auth.MAX_ATTEMPTS):
            protected.post("/api/auth/login", json={"password": "mal"})
        r = protected.post("/api/auth/login", json={"password": "mal"})
        assert r.status_code == 429
        assert r.json()["detail"]["retry_after_seconds"] > 0

    def test_the_lock_applies_even_to_the_right_password(self, protected):
        """Si no, bastaría con seguir probando hasta acertar."""
        for _ in range(auth.MAX_ATTEMPTS):
            protected.post("/api/auth/login", json={"password": "mal"})
        assert protected.post("/api/auth/login", json={"password": PASSWORD}).status_code == 429

    def test_a_success_clears_the_counter(self, protected):
        for _ in range(auth.MAX_ATTEMPTS - 1):
            protected.post("/api/auth/login", json={"password": "mal"})
        assert protected.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200
        auth.reset_attempts()
        for _ in range(auth.MAX_ATTEMPTS - 1):
            protected.post("/api/auth/login", json={"password": "mal"})
        assert protected.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200

    def test_a_forged_forwarded_header_does_not_reset_the_limit(self, protected):
        """X-Forwarded-For la pone cualquiera; si contara, el limite no serviria."""
        for _ in range(auth.MAX_ATTEMPTS):
            protected.post("/api/auth/login", json={"password": "mal"},
                           headers={"X-Forwarded-For": "1.2.3.4"})
        r = protected.post("/api/auth/login", json={"password": "mal"},
                           headers={"X-Forwarded-For": "9.9.9.9"})
        assert r.status_code == 429


# ---------------------------------------------------------------------------
class TestSessionStorage:
    def test_the_token_is_stored_hashed_not_in_the_clear(self, protected):
        """Quien lea la base de datos no debe poder suplantar una sesión."""
        from app.db import get_conn

        protected.post("/api/auth/login", json={"password": PASSWORD})
        token = protected.cookies.get(auth.COOKIE_NAME)
        with get_conn() as conn:
            filas = conn.execute("SELECT token_hash FROM sessions").fetchall()
        assert filas
        assert all(f["token_hash"] != token for f in filas)

    def test_an_expired_session_stops_working(self, protected, monkeypatch):
        from datetime import datetime, timedelta, timezone

        from app.db import get_conn

        protected.post("/api/auth/login", json={"password": PASSWORD})
        pasado = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with get_conn() as conn:
            conn.execute("UPDATE sessions SET expires_at = ?", (pasado,))
        assert protected.get("/api/portfolio").status_code == 401


# ---------------------------------------------------------------------------
class TestLocalStaysOpen:
    """Sin contraseña, en tu máquina, nada cambia."""

    def test_without_a_password_everything_works_as_before(self, tmp_path, monkeypatch):
        db = tmp_path / "abierta.db"
        monkeypatch.setattr("app.config.DB_PATH", db)
        monkeypatch.setattr("app.db.DB_PATH", db)
        monkeypatch.setattr(auth, "setting", lambda name, default="": default)

        from app.main import app

        with TestClient(app) as c:
            assert c.get("/api/health").json()["auth_required"] is False
            assert c.get("/api/profile").status_code == 200
            assert c.get("/api/auth/status").json()["auth_required"] is False

    def test_it_warns_that_publishing_like_this_would_be_open(self, tmp_path, monkeypatch):
        db = tmp_path / "abierta2.db"
        monkeypatch.setattr("app.config.DB_PATH", db)
        monkeypatch.setattr("app.db.DB_PATH", db)
        monkeypatch.setattr(auth, "setting", lambda name, default="": default)

        from app.main import app

        with TestClient(app) as c:
            aviso = c.get("/api/auth/status").json()["notice"]
        assert "cualquiera" in aviso.lower()
