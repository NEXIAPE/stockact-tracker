"""
Aísla la suite de la configuración REAL de quien la ejecuta.

Fallo encontrado en la máquina del usuario y no en la mía: dos tests de
proveedores de precios fallaban allí y pasaban aquí. La causa no estaba en el
código sino en su ``.env``, que lleva ``PRICE_PROVIDERS=yahoo,stooq`` desde que
su red empezó a devolver 403 en Stooq. Los tests que dan por hecho el orden por
defecto veían el suyo y fallaban.

Un test que pasa en una máquina y falla en otra por la configuración personal
de cada una no está midiendo el código: está midiendo el ordenador. Y una suite
en la que dos fallos son «normales, es mi .env» deja de servir para lo único
que sirve, que es avisar cuando algo se rompe de verdad.

Así que se corta de raíz, para toda la suite y no sólo para los dos tests que
se quejaron hoy: se apunta el lector de configuración a un archivo que no
existe y se retiran del entorno los ajustes de la aplicación. Un test que
necesite un valor concreto lo pone él mismo con ``monkeypatch.setenv``, que es
como debe ser: explícito y visible en el propio test.

Esto tiene que ejecutarse ANTES de que se importe ``app.config``, porque ese
módulo lee el archivo una sola vez al importarse. pytest carga los conftest
antes que los módulos de test, así que este archivo es el sitio correcto.

El guardián que comprueba que esto sigue funcionando está en
``tests/test_suite_isolation.py``: pytest no recoge tests desde un conftest.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- 1. Que no se lea ningún .env real -------------------------------------
# La ruta no existe a propósito: _load_env_file devuelve {} y la configuración
# se queda en sus valores por defecto.
ENV_FILE_DE_MENTIRA = (
    Path(__file__).resolve().parent / "tests" / ".env-inexistente-en-los-tests"
)
os.environ["INVEST_ENV_FILE"] = str(ENV_FILE_DE_MENTIRA)

# --- 2. Que no se cuele una variable de entorno de verdad ------------------
# Alguien puede tener exportada su clave de Finnhub o su orden de proveedores.
# monkeypatch.setenv sigue funcionando dentro de cada test y se deshace solo.
AJUSTES_DE_LA_APP = (
    "PRICE_PROVIDERS",
    "FINNHUB_API_KEY",
    "TWELVEDATA_API_KEY",
    "INVEST_CONTACT",
    "INVEST_DB",
    "INVEST_CACHE",
    "STOCKACT_DB",
    "APP_PASSWORD",
    "APP_PASSWORD_HASH",
    "APP_INSECURE_COOKIE",
)
for _nombre in AJUSTES_DE_LA_APP:
    os.environ.pop(_nombre, None)
