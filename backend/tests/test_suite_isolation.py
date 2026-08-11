"""
Guardián del aislamiento de la suite (ver ``backend/conftest.py``).

Sin esto, si alguien mueve o renombra el conftest, o cambia el nombre de la
variable de entorno, los tests volverían a leer el ``.env`` de cada máquina.
El síntoma sería el de siempre: fallos intermitentes que dependen de quién
ejecute la suite y que cuesta atribuir a su causa real.
"""

from __future__ import annotations

import os

import conftest
from app import config


def test_no_real_env_file_is_read():
    assert not config.ENV_FILE.exists(), (
        f"Los tests están leyendo un .env real ({config.ENV_FILE}). "
        "Su resultado pasaría a depender de cómo tenga configurada su máquina "
        "quien los ejecute, que es justo lo que el conftest evita."
    )
    assert config._FILE_VALUES == {}


def test_no_app_setting_leaks_in_from_the_environment():
    puestas = [n for n in conftest.AJUSTES_DE_LA_APP if os.getenv(n) is not None]
    assert not puestas, f"Estos ajustes se colaron del entorno real: {puestas}"


def test_the_default_provider_order_is_what_the_tests_assume():
    """La regresión concreta que motivó todo esto.

    Con ``PRICE_PROVIDERS=yahoo,stooq`` en el .env del usuario, los tests que
    dan por hecho que Stooq va primero fallaban en su máquina y pasaban en la
    mía. (``order()`` deja fuera twelvedata mientras no haya clave, así que se
    comprueba la cabeza de la lista, que es lo que esos tests asumen.)
    """
    from app.providers import prices

    assert prices.order()[0] == "stooq"
