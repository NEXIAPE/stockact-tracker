#!/usr/bin/env python3
"""
Genera la contraseña para publicar la herramienta en internet.

    .venv/bin/python backend/set_password.py

Pide una contraseña, comprueba que no sea débil y escribe su HASH en el .env.
La contraseña en sí no se guarda en ningún sitio: si la olvidas, hay que poner
otra. Eso es lo correcto — un sistema que puede recuperar tu contraseña es un
sistema que la tiene guardada.

Antes de publicar, léete la advertencia que imprime al final. No es relleno.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.auth import hash_password, password_problems  # noqa: E402
from app.config import ENV_FILE  # noqa: E402


def escribir_en_env(linea_clave: str, valor: str) -> None:
    """Añade o reemplaza una clave del .env sin tocar el resto."""
    lineas = []
    if ENV_FILE.exists():
        # utf-8-sig por el BOM que escribe PowerShell; ya nos mordió una vez.
        lineas = ENV_FILE.read_text(encoding="utf-8-sig").splitlines()

    salida, reemplazada = [], False
    for linea in lineas:
        if linea.strip().startswith(f"{linea_clave}="):
            salida.append(f"{linea_clave}={valor}")
            reemplazada = True
        else:
            salida.append(linea)
    if not reemplazada:
        salida.append(f"{linea_clave}={valor}")

    ENV_FILE.write_text("\n".join(salida) + "\n", encoding="utf-8")


def main() -> int:
    print("=" * 70)
    print("CONTRASEÑA PARA PUBLICAR LA HERRAMIENTA")
    print("=" * 70)
    print()
    print("Esta contraseña será lo ÚNICO que separe tu cartera, tu efectivo y tu")
    print("perfil de cualquiera que dé con la dirección. Elígela en consecuencia:")
    print("larga, que no uses en ningún otro sitio, y guardada en un gestor.")
    print()

    password = getpass.getpass("  Contraseña: ")
    if not password:
        print("\nCancelado: no escribiste nada.")
        return 1

    repetida = getpass.getpass("  Repítela:   ")
    if password != repetida:
        print("\nNo coinciden. No se ha cambiado nada.")
        return 1

    problemas = password_problems(password)
    if problemas:
        print()
        for p in problemas:
            print(f"  AVISO: {p}")
        print()
        if input("  ¿Usarla igualmente? (escribe SI para continuar): ").strip() != "SI":
            print("\nCancelado. No se ha cambiado nada.")
            return 1

    escribir_en_env("APP_PASSWORD_HASH", hash_password(password))

    print()
    print(f"  Hash guardado en {ENV_FILE}")
    print("  La contraseña en claro NO se guarda en ninguna parte.")
    print()
    print("=" * 70)
    print("ANTES DE PUBLICAR, LEE ESTO")
    print("=" * 70)
    print("""
  1. HTTPS obligatorio. Sin él, la contraseña viaja en claro por la red y
     cualquiera en el camino puede leerla. Todas las plataformas de despliegue
     habituales lo dan hecho; si montas tu propio servidor, es cosa tuya.

  2. El .env NO se sube al repositorio (está en .gitignore). En la plataforma
     donde publiques, configura APP_PASSWORD_HASH como variable de entorno.

  3. La base de datos es un archivo. Si la plataforma tiene disco efímero,
     PERDERÁS tus datos en cada despliegue. Necesitas un volumen persistente y
     apuntar INVEST_DB ahí.

  4. Exporta tus datos de vez en cuando desde Ajustes. Es un archivo y es tuyo.

  5. Sigue siendo una herramienta de SOLO LECTURA: no envía órdenes a ningún
     bróker. Publicarla no cambia eso.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
