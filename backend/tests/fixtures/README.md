# Fixtures de los proveedores

**Qué son:** payloads de ejemplo escritos a mano siguiendo el formato
DOCUMENTADO de cada fuente (columnas, nombres de campo, formatos de fecha).

**Qué NO son:** capturas reales de tráfico. No se grabaron desde las fuentes.

Sirven para probar que los parsers manejan bien la ESTRUCTURA esperada: orden de
columnas, formatos de fecha, campos ausentes, filas corruptas, unidades. No
demuestran que la fuente siga sirviendo exactamente esto hoy.

Para comprobar la realidad hay un diagnóstico que golpea las fuentes de verdad
desde tu máquina:

    .venv/bin/python backend/diagnose.py
