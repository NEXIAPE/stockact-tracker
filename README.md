# Rastreador modular de divulgaciones STOCK Act (v1: solo Cámara)

Una herramienta sencilla y **modular** para seguir las divulgaciones de
transacciones bursátiles que los miembros del Congreso de EE. UU. están
obligados a publicar bajo la **STOCK Act**. Esta versión 1 trae **activo el
conector de la Cámara de Representantes (House)**; el del Senado y el de un
agregador externo vienen como **esqueletos desactivados**, listos para que los
actives cuando quieras.

> ⚠️ **Este informe es DESCRIPTIVO, no da recomendaciones de inversión.** Sólo
> resume datos que ya son públicos. No es asesoramiento financiero.

---

## ¿Qué hace?

1. **Recolecta** divulgaciones desde uno o más conectores (fuentes).
2. **Consolida**: elimina duplicados exactos y resuelve enmiendas (una
   corrección reemplaza al dato original).
3. **Persiste** en una base de datos SQLite y detecta **novedades** entre
   ejecuciones (sólo te muestra lo nuevo).
4. **Genera un informe diario en texto** con:
   - Divulgaciones nuevas.
   - Top 10 tickers de los últimos 30 días.
   - Desglose por sector.

---

## Para principiantes: cómo empezar

Necesitas **Python 3.9 o superior**. No hay que instalar nada más (sólo se usa
la librería estándar).

### 1. Comprueba que todo funciona (sin tocar Internet)

```bash
python main.py --self-test
```

Esto valida la tubería **offline** usando `samples/sample_FD.xml`. Debe
**eliminar 1 duplicado** y **fusionar 1 enmienda**, y terminar con `EXITO ✅`.

### 2. Procesar un archivo local de ejemplo (tubería completa)

```bash
python main.py --ingest-file samples/sample_FD.xml
```

Esto consolida, guarda en `stockact.db` y escribe un informe
`informe_AAAA-MM-DD.txt`. (Ambos están en `.gitignore` y se regeneran.)

### 3. Ejecución "en vivo"

```bash
python main.py
```

En v1 el `fetch` en vivo de la Cámara queda como punto de extensión (ver
abajo). El esqueleto de descarga ya es **cortés** (User-Agent + rate limiting).

---

## Estructura del proyecto

```
.
├── main.py            # Orquestador + modo --self-test
├── models.py          # Formato común: la clase Disclosure
├── consolidation.py   # Dedup exacto + resolución de enmiendas
├── storage.py         # SQLite + detección incremental de novedades
├── report.py          # Informe diario en texto (descriptivo)
├── httpclient.py      # HTTP cortés: User-Agent + rate limiting + reintentos
├── sectors.py         # Mapa ticker -> sector (offline)
├── connectors/
│   ├── base.py        # Interfaz común de conector
│   ├── house.py       # Cámara — ACTIVO
│   ├── senate.py      # Senado — esqueleto DESACTIVADO
│   └── aggregator.py  # Agregador externo — esqueleto DESACTIVADO
├── samples/
│   └── sample_FD.xml  # Datos de muestra para --self-test
├── scripts/
│   ├── cron_mac.sh
│   ├── cron_linux.sh
│   └── cron_windows.bat
└── requirements.txt   # (vacío: sólo librería estándar)
```

---

## Conectores modulares

Todos los conectores producen objetos `Disclosure` (formato común), así que las
capas superiores no dependen de la fuente.

| Conector   | Estado        | Fuente                                            |
|------------|---------------|---------------------------------------------------|
| House      | ✅ ACTIVO     | Clerk de la Cámara (financial disclosures / PTR)  |
| Senate     | ⛔ desactivado | eFD del Senado (`efdsearch.senate.gov`)           |
| Aggregator | ⛔ desactivado | Agregador externo de terceros (a tu elección)     |

### Cómo activar el Senado

1. Abre `connectors/senate.py` y pon `enabled = True`.
2. Implementa `fetch()` siguiendo las instrucciones del encabezado del archivo
   (aceptar el acuerdo del portal, buscar, abrir cada PTR, mapear a `Disclosure`).
3. Usa siempre `self.http` para respetar User-Agent y rate limiting.

### Cómo activar el agregador externo

1. **Revisa los términos de uso y la licencia** del agregador que elijas.
2. Abre `connectors/aggregator.py`, pon `enabled = True`, configura `API_BASE`
   (y la API key por variable de entorno, no hardcodeada).
3. Implementa `fetch()` y mapea a `Disclosure` con `source = "aggregator"`.

### Cómo activar el `fetch` en vivo de la Cámara

El parseo (`parse`) ya está implementado para el esquema de muestra. Para datos
reales necesitas descargar el ZIP anual del Clerk
(`disclosures-clerk.house.gov`) y adaptar el parseo a su formato concreto
(índice XML + PTR). El método `fetch()` en `connectors/house.py` documenta el
endpoint y deja el punto de extensión.

---

## ⚠️ Advertencias importantes (léelas)

- **Rate limits.** Las fuentes oficiales pueden limitar o bloquear clientes
  agresivos. El `HttpClient` aplica un retardo mínimo entre solicitudes y se
  identifica con un User-Agent. **No reduzcas el intervalo** ni lances muchas
  ejecuciones seguidas. **Una vez al día es más que suficiente.** Pon tu
  contacto real en `httpclient.py` (`CONTACT`).

- **Términos de uso.** Cada fuente (Cámara, Senado, agregadores) tiene sus
  propios términos y licencia. Es **tu responsabilidad** leerlos y cumplirlos
  antes de activar un conector, especialmente con agregadores comerciales.

- **Desfase legal de ~45 días.** Los Periodic Transaction Reports (PTR) pueden
  presentarse hasta **~45 días después** de la operación (y a veces más). Lo que
  veas "hoy" describe el **pasado**; no es información en tiempo real.

- **No es asesoramiento financiero.** El informe es **descriptivo**. No genera,
  ni debe generar, recomendaciones de compra/venta. El `--self-test` incluso
  verifica que el informe no contenga recomendaciones.

---

## Programación automática (cron)

Ejecuta el rastreador **una vez al día** (suficiente, dado el desfase de ~45
días). Hay scripts listos en `scripts/`:

- **macOS:** `scripts/cron_mac.sh` (vía `crontab`)
- **Linux:** `scripts/cron_linux.sh` (vía `crontab` o systemd timer)
- **Windows:** `scripts/cron_windows.bat` (vía Programador de tareas)

Cada script incluye las instrucciones de instalación en su encabezado.

---

## Persistencia y novedades

- Los datos se guardan en `stockact.db` (SQLite).
- Cada divulgación se identifica por su **clave de negocio** (legislador +
  ticker + tipo + fecha + monto). Al guardar, sólo se insertan las **no vistas**;
  esas son las novedades del día.
- `stockact.db` y los informes están en `.gitignore`: son artefactos locales
  que se regeneran.

---

## Licencia y datos

Este código es una herramienta de seguimiento. Los **datos** provienen de
fuentes oficiales de divulgación pública (y, si lo activas, de terceros con su
propia licencia). Respeta siempre los términos de cada fuente.
