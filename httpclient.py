"""
Cliente HTTP cortés: User-Agent identificable + rate limiting simple.

Las fuentes oficiales (Clerk de la Cámara, Senado) pueden bloquear o limitar
clientes que no se identifican o que golpean demasiado rápido. Este wrapper:

  * Fija un User-Agent descriptivo con contacto (configúralo en CONTACT).
  * Aplica un retardo mínimo entre solicitudes (rate limiting de cortesía).
  * Reintenta con backoff exponencial ante errores transitorios.

Usa la librería estándar (urllib) para no requerir dependencias externas.
"""

from __future__ import annotations

import time
import urllib.request
import urllib.error


# Cámbialo por algo que te identifique. Las fuentes oficiales lo aprecian y
# es la práctica correcta para scraping/consumo responsable.
CONTACT = "stockact-tracker (contacto: tu-email@example.com)"
DEFAULT_USER_AGENT = f"Mozilla/5.0 (compatible; {CONTACT})"


class HttpClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval: float = 1.5,
        timeout: float = 30.0,
        max_retries: int = 4,
    ):
        self.user_agent = user_agent
        self.min_interval = min_interval  # segundos mínimos entre requests
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.min_interval - elapsed
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str) -> bytes:
        """GET con rate limiting + reintentos. Devuelve el cuerpo en bytes."""
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    self._last_request_ts = time.monotonic()
                    return resp.read()
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                self._last_request_ts = time.monotonic()
                last_err = exc
                backoff = 2.0 ** attempt  # 1, 2, 4, 8...
                time.sleep(backoff)
        raise RuntimeError(f"GET falló tras {self.max_retries} intentos: {url}") from last_err
