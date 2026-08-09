# Herramienta de inversión personal (edición de un solo usuario)

Te ayuda a **decidir** en qué invertir: te sugiere ideas de compra / mantener /
evitar / vender, con sus razones, sus números citados, sus riesgos y su
contra-argumento. Tú decides y **tú ejecutas a mano** en tu bróker.

> **Esta herramienta NUNCA envía órdenes ni se conecta a un bróker para operar.**
> Es de solo lectura. Y **no es asesoría financiera ni tributaria**: invertir
> desde Perú en un bróker extranjero tiene implicancias que debes consultar con
> un contador.

Este repositorio contiene además el **rastreador STOCK Act** original (CLI en
Python puro), que se conserva y se integra como señal de contexto. Ver
[más abajo](#el-rastreador-stock-act-original).

---

## Qué hace

| Pantalla | Qué te da |
|---|---|
| **Perfil / onboarding** | Define capital, aporte mensual, riesgo, horizonte y objetivos → deriva una estrategia mínima, explicando el porqué de cada regla. |
| **Briefing diario** | Resumen priorizado: cómo va tu cartera, alertas, desvíos frente a tu plan e ideas que encajan contigo. |
| **Analizar** | Escribe un símbolo y recibe la recomendación estructurada completa. |
| **Cartera** | Registras lo que ya tienes; se valora con precios reales y se revisa concentración y diversificación. |
| **Watchlist** | Símbolos que sigues, con criterios propios de aviso. |
| **Alertas** | Noticias, movimientos fuertes, criterios cumplidos y desvíos de cartera — siempre como «vale la pena mirar». |
| **Ajustes** | Estado de las fuentes, exportar todo, borrar todo. |

### Cada recomendación trae, sin excepción

Idea clara y tamaño sugerido · tesis en lenguaje simple · evidencia con números
reales y citados · riesgos concretos · **el argumento más fuerte en contra** ·
encaje con tu cartera y tu estrategia · nivel de confianza y qué le falta.

---

## Las reglas duras (y cómo se hacen cumplir)

No son buenas intenciones: son validaciones que **bloquean la respuesta**.

| Regla | Cómo se hace cumplir | Dónde |
|---|---|---|
| **Nunca un número inventado** | Todo valor viaja en un `DataPoint` con fuente y fecha. Un guardián escanea la prosa y falla si aparece una cifra que no procede de un dato citado. Lo que falta se devuelve como `Missing` con su motivo, nunca como cero. | `core/datapoint.py`, `core/guards.py` |
| **Ninguna recomendación sin riesgos ni contra-caso** | Validación obligatoria antes de devolver; si falta, error 500 explicando el defecto. El frontend lo vuelve a comprobar y se niega a pintarla. | `core/guards.py`, `components/Recommendation.jsx` |
| **Sugiere, nunca ejecuta** | El cliente HTTP sólo expone `get`. Un test escanea todo el repositorio buscando rastros de ejecución de órdenes y falla si aparece alguno. | `providers/http.py`, `tests/test_hard_rules.py` |
| **Nada de urgencia ni FOMO** | Linter de texto sobre alertas, ideas y recomendaciones: rechaza «compra ya», «oportunidad única», signos de exclamación… | `core/guards.py` |
| **Honestidad sobre lo que falta** | Cada dato lleva su antigüedad; el briefing termina con el estado de las fuentes; «no pude consultar la SEC» nunca se confunde con «no existe». | `core/briefing.py`, `providers/edgar.py` |
| **Tus datos son tuyos** | Un solo archivo SQLite local, exportable e íntegramente borrable. | `/api/data/export`, `/api/data/wipe` |

### Protecciones de principiante

- Sesgo explícito y **visible en el desglose de la puntuación** hacia ETFs
  amplios frente a acciones individuales.
- Tope estricto por acción individual (5 % mientras seas principiante).
- Aviso si te sobre-concentras en un activo, un sector o en acciones sueltas.
- El tamaño sugerido nunca se come el colchón mínimo de efectivo de tu estrategia.
- Recordatorio permanente de que esto no es asesoría profesional ni tributaria.

---

## Fuentes de datos

Opción elegida: **gratuitas sin clave + una clave gratuita opcional**.

| Fuente | Aporta | Costo | Límites honestos |
|---|---|---|---|
| **Stooq** | Precios de cierre diario, histórico | gratis, sin clave | Sólo cierre diario, sin intradía. Sin garantía de servicio. |
| **SEC EDGAR (XBRL)** | Fundamentales oficiales (10-K) | gratis, sin clave | No cubre ETFs. Datos anuales. Exige User-Agent identificable. |
| **RSS (Yahoo Finance + SEC)** | Titulares y presentaciones oficiales | gratis, sin clave | Cobertura desigual. Los titulares son interpretación, no hechos. |
| **Finnhub** *(opcional)* | Cotización fresca, PER, beta, márgenes | plan gratuito con clave | Requiere `FINNHUB_API_KEY`. Si se agota la cuota, se dice y se cae a las fuentes sin clave. |
| **STOCK Act local** | Divulgaciones del Congreso EE. UU. | gratis | Desfase de hasta ~45 días. **Peso cero** en la recomendación: es contexto. |

### Lo que la herramienta NO tiene, a propósito

- **Sentimiento de mercado.** Ninguna fuente gratuita lo da de forma fiable, así
  que ese bloque aparece vacío en vez de relleno con algo inventado.
- **Ratio de gastos y composición de ETFs.** No están disponibles de forma
  fiable. En vez de escribirlos de memoria en el código (que sería inventarlos),
  el catálogo enlaza la ficha oficial del emisor y tú registras el dato con la
  fecha en que lo leíste; entonces aparece citado como cualquier otro.

---

## Puesta en marcha

### Windows (PowerShell) — dos comandos

```powershell
powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1   # una sola vez
powershell -ExecutionPolicy Bypass -File scripts\arrancar_windows.ps1   # cada vez que la uses
```

El instalador comprueba Python y Node, crea el entorno, instala todo, te pide tu
email (y la clave de Finnhub si la quieres) y termina ejecutando el diagnóstico
de fuentes. El de arranque abre el motor y la interfaz en dos ventanas y te lleva
al navegador.

### macOS y Linux — a mano

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
INVEST_CONTACT="tu-email@ejemplo.com" .venv/bin/uvicorn app.main:app --app-dir backend --reload
# API en http://127.0.0.1:8000  ·  documentación en /docs

# Frontend (otra terminal)
cd frontend && npm install && npm run dev
# Interfaz en http://localhost:5173
```

Primer uso: entra en **Perfil**, completa el onboarding, registra tu cartera y
tu efectivo, y ya puedes analizar símbolos y recibir el briefing.

### Variables de entorno

| Variable | Para qué | Por defecto |
|---|---|---|
| `INVEST_CONTACT` | Tu email en el User-Agent. **La SEC lo exige**; ponlo. | `usuario-personal@example.com` |
| `FINNHUB_API_KEY` | Activa la fuente opcional con clave. | vacío (desactivada) |
| `INVEST_DB` | Ruta de tu base de datos. | `personal_invest.db` |
| `INVEST_CACHE` | Caché de respuestas de las fuentes. | `.data_cache/` |
| `STOCKACT_DB` | Base del rastreador STOCK Act. | `stockact.db` |

### Comprobar que las fuentes responden de verdad

Los tests no tocan la red, así que **no pueden demostrar que las fuentes te
funcionen a ti**. Para eso hay un diagnóstico que las golpea de verdad desde tu
máquina y te dice, una por una, qué respondió y qué no:

```bash
.venv/bin/python backend/diagnose.py               # AAPL y VOO por defecto
.venv/bin/python backend/diagnose.py --ticker MSFT --etf VTI
```

Sale con código 1 si falla alguna fuente obligatoria. Ejecútalo la primera vez
y cada vez que algo parezca raro (precios que no cambian, fundamentales
ausentes, ninguna noticia).

### Briefing automático cada día

Para que al abrir la herramienta ya esté todo calculado:

```bash
.venv/bin/python backend/daily.py                  # refresca alertas + escribe el briefing
```

Hay scripts listos para programarlo en `scripts/briefing_diario.sh` (Linux y
macOS, vía `crontab`) y `scripts/briefing_diario.bat` (Windows, vía Programador
de tareas). **Una vez al día es suficiente**: las fuentes dan cierres diarios, y
mirar la cartera a todas horas es una forma conocida de decidir peor.

### Tests

```bash
cd backend && ../.venv/bin/python -m pytest        # 130 tests
```

| Archivo | Qué cubre |
|---|---|
| `test_hard_rules.py` | Las cuatro reglas innegociables y la honestidad sobre datos viejos. |
| `test_engine.py` | Derivación de estrategia, indicadores, cartera, guardianes integrados. |
| `test_providers.py` | Los parsers de cada fuente contra payloads con la forma documentada. |
| `test_api.py` | La API completa, incluidas regresiones de fallos reales encontrados probando. |

**No tocan la red**: los proveedores se sustituyen por dobles deterministas y
fixtures. Eso prueba la lógica, no la disponibilidad — para la disponibilidad
está `diagnose.py`.

---

## El rastreador STOCK Act original

El CLI que ya existía en este repositorio se conserva intacto y funcionando:

```bash
python main.py --self-test                    # valida la tubería offline
python main.py --ingest-file samples/sample_FD.xml
```

Rastrea las divulgaciones de operaciones bursátiles que los miembros del
Congreso de EE. UU. deben publicar. La herramienta de inversión lo lee, si está
disponible, y lo muestra como **contexto de color** en el análisis de un ticker.

**No influye en ninguna recomendación.** Los Periodic Transaction Reports pueden
presentarse hasta ~45 días después de la operación: describen el pasado, no el
presente, y no son una señal de compra ni de venta.

Los conectores del Senado y del agregador externo siguen como esqueletos
desactivados; sus instrucciones de activación están en cada archivo.

---

## Estructura

```
backend/app/
  core/        datapoint · guards · profile · portfolio · indicators
               universe · recommendation · ideas · alerts · briefing
  providers/   stooq · edgar · news_rss · finnhub · stockact · http
  routers/     profile · portfolio · watchlist · analysis · briefing · data
backend/diagnose.py   comprueba las fuentes contra la realidad
backend/daily.py      briefing diario sin interfaz (para cron)
backend/tests/ test_hard_rules · test_engine · test_providers · test_api
frontend/src/  pages/ · components/ · api.js · styles.css

main.py, connectors/, consolidation.py, storage.py, report.py, sectors.py
    → rastreador STOCK Act original (Python puro, sin dependencias)
```

---

## Advertencia final

Esta herramienta es un apoyo a la decisión construido para un único usuario. No
predice el futuro, no sustituye a un asesor y su motor es un conjunto de reglas
simples y auditables, no una inteligencia de mercado. Cuando no sepa algo, te lo
dirá. Cuando te sugiera algo, te dirá también por qué podría estar equivocada.
