"""
Cliente HTTP cortés + caché en disco.

Mantiene la misma disciplina que el ``httpclient.py`` del rastreador STOCK Act
que ya vivía en este repo (User-Agent identificable, rate limiting, reintentos)
y le añade caché en disco para no golpear a fuentes gratuitas más de lo justo.

IMPORTANTE: este cliente sólo hace GET. No existe ninguna ruta de escritura
hacia ningún servicio externo. La herramienta es de solo lectura.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from ..config import CACHE_DIR, USER_AGENT


class FetchError(RuntimeError):
    """No se pudo obtener el dato. Se propaga como «dato no disponible»,
    nunca como un cero silencioso."""


class PoliteClient:
    def __init__(
        self,
        min_interval: float = 0.6,
        timeout: float = 20.0,
        max_retries: int = 3,
        cache_dir: Optional[Path] = None,
    ):
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir or CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_ts = 0.0

    # -- caché ------------------------------------------------------------
    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def cache_read(self, key: str, ttl: int) -> Optional[bytes]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None
        if time.time() - meta.get("ts", 0) > ttl:
            return None
        return meta.get("body", "").encode("utf-8")

    def cache_write(self, key: str, body: bytes) -> None:
        try:
            self._cache_path(key).write_text(
                json.dumps({"ts": time.time(), "body": body.decode("utf-8", "replace")}),
                encoding="utf-8",
            )
        except OSError:
            pass  # la caché es una optimización, nunca un requisito

    def cache_clear(self) -> int:
        n = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
        return n

    # -- red ---------------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_ts)
        if wait > 0:
            time.sleep(wait)

    def get(
        self,
        url: str,
        *,
        ttl: int = 0,
        headers: Optional[dict] = None,
        cache_key: Optional[str] = None,
    ) -> bytes:
        key = cache_key or url
        if ttl:
            cached = self.cache_read(key, ttl)
            if cached is not None:
                return cached

        request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if headers:
            request_headers.update(headers)

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            self._throttle()
            req = urllib.request.Request(url, headers=request_headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    self._last_ts = time.monotonic()
                    body = resp.read()
                if ttl:
                    self.cache_write(key, body)
                return body
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                self._last_ts = time.monotonic()
                last_err = exc
                if attempt < self.max_retries - 1:
                    time.sleep(1.5 ** attempt)

        # Si la red falla pero hay algo en caché aunque esté vencido, es mejor
        # devolverlo marcado como viejo que no devolver nada: el motor ya baja
        # la confianza por antigüedad y el frontend muestra la fecha del dato.
        stale = self.cache_read(key, ttl=10 ** 9)
        if stale is not None:
            return stale

        raise FetchError(f"No se pudo obtener {url}: {last_err}")


_client: Optional[PoliteClient] = None


def client() -> PoliteClient:
    global _client
    if _client is None:
        _client = PoliteClient()
    return _client
