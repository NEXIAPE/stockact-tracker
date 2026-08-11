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
| **Briefing diario** | Arriba del todo, en una línea: **¿hay algo que hacer hoy?** Debajo, cartera, alertas, desvíos e ideas. |
| **Analizar** | Escribe un símbolo y recibe la recomendación estructurada completa. |
| **Cartera** | Registras lo que ya tienes; se valora con precios reales y se revisa concentración y diversificación. Incluye **tu tesis** de cada posición y **cómo te va frente a un fondo amplio**. |
| **Watchlist** | Símbolos que sigues, con criterios propios de aviso. |
| **Alertas** | Noticias, movimientos fuertes, criterios cumplidos y desvíos de cartera — siempre como «vale la pena mirar». |
| **Ajustes** | Estado de las fuentes, exportar todo, borrar todo. |

### Comprar, mantener, recortar, evitar o vender

La herramienta revisa también lo que YA tienes: tus posiciones entran en el
briefing diario y se analizan como cualquier candidato. Tres decisiones que se
mantienen deliberadamente separadas:

- **Vender** exige **deterioro real del negocio o de la tendencia de fondo**.
  Que el precio haya caído no basta: si la tesis sigue en pie, un precio más
  bajo abarata comprar, no justifica huir. Vender por haber caído es la forma
  más común de convertir una pérdida temporal en definitiva.
- **Recortar** es lo que corresponde cuando algo pesa más que tu propio tope.
  No es deshacer la posición, es devolverla a su tamaño — y suele poder
  corregirse sin vender nada, dirigiendo los próximos aportes a otra cosa.
- **No poder comprar más** (sin efectivo, o ya en tu cupo) **nunca** es motivo
  para vender. Son preguntas distintas y el motor las puntúa por separado.

Toda idea de vender o recortar añade sus riesgos propios: que realizar la
operación la vuelve definitiva, su coste tributario, y lo caro que sale acertar
dos veces al intentar volver a entrar.

### «Hoy no hay nada que hacer»

Lo primero que ves al abrir responde una sola pregunta, en grande y en una
línea. La mayoría de los días la respuesta correcta es que no hay nada que
hacer, y **decirlo alto y claro es una función del producto, no un hueco**: una
herramienta que cada mañana parece tener algo urgente acaba enseñándote a operar
de más. Cuando sí hay algo, se lista ordenado por lo que más suele importar, con
el enlace a donde mirarlo, y se dice explícitamente que no pide que actúes hoy.

### Las ideas NO son un descubrimiento diario

Verás casi siempre **los mismos símbolos**. Los candidatos salen de una lista
corta y fija: tu watchlist, seis ETFs amplios (VT, VTI, VOO, VXUS, BND, AGG) y
lo que ya tienes, para revisar si sigue encajando. Máximo ocho, se muestran
hasta cuatro.

Lo que cambia cada día es **el veredicto, no el reparto**: el mismo fondo puede
pasar de «mantener» a «comprar» porque bajó de precio, porque te entró efectivo
o porque tu peso se desvió.

Es deliberado. No hay ningún buscador de «acciones de moda», porque proponer lo
que más sube es la forma más rápida de que compres caro, y una herramienta que
cada mañana presenta algo nuevo y emocionante enseña a operar de más. **La
palanca eres tú**: si quieres ver otra cosa, añádela a tu watchlist y entra en
la rotación.

### Tu tesis: la única señal de venta que vale

Al registrar una posición anotas **por qué la compraste** y **qué te haría dejar
de creerlo**. Sin eso, lo único que la herramienta puede mirar para opinar sobre
vender es el precio — y el precio es la peor señal posible.

La herramienta **no evalúa tu tesis** y no finge hacerlo: es texto libre y un
motor de reglas no puede juzgarlo. Lo que hace es ponértela delante cada vez que
revisa la posición, recordarte literalmente lo que tú escribiste como motivo
para salir cuando aparecen señales de deterioro, y avisarte si llevas más de
seis meses sin releerla. Si falta, se dice: aparece como hueco en el nivel de
confianza y en el briefing.

### Cómo te va de verdad

La pregunta incómoda no es «¿he ganado dinero?» sino **«¿me habría ido mejor
comprando un fondo amplio y no volviendo a mirar?»**. Se reconstruye qué habría
pasado si cada aporte que registraste hubiera ido, ese mismo día, a un índice de
referencia. Comparar rentabilidades a secas sería tramposo porque no invertiste
todo el mismo día.

Dos salvaguardas contra un resultado halagüeño y falso: si tu bitácora no cubre
todas tus posiciones **no se compara nada** (el valor de lo no registrado
contaría como ganancia salida de la nada), y con menos de un año o menos de
cinco operaciones se dice que aún es casi todo suerte.

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
| **Stooq** | Precios de cierre diario, histórico | gratis, sin clave | Sólo cierre diario, sin intradía. Sin garantía de servicio, y **no accesible desde todas las redes**. |
| **Yahoo Finance (chart)** | Precios de cierre diario, respaldo del anterior | gratis, sin clave | Endpoint no oficial: puede cambiar sin aviso. Por eso es respaldo, no principal. |
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

### Configuración: el archivo `.env`

Copia `.env.example` como `.env` en la raíz y edítalo. **La aplicación lo lee
siempre**, la lances como la lances: interfaz, diagnóstico, briefing diario o
cron. Una variable de entorno real tiene prioridad sobre el archivo.

| Variable | Para qué | Por defecto |
|---|---|---|
| `INVEST_CONTACT` | Tu email en el User-Agent. **La SEC lo exige**; ponlo. | `usuario-personal@example.com` |
| `FINNHUB_API_KEY` | Activa la fuente opcional con clave. | vacío (desactivada) |
| `INVEST_DB` | Ruta de tu base de datos. | `personal_invest.db` |
| `INVEST_CACHE` | Caché de respuestas de las fuentes. | `.data_cache/` |
| `STOCKACT_DB` | Base del rastreador STOCK Act. | `stockact.db` |
| `PRICE_PROVIDERS` | Orden de los proveedores de precios, separados por comas. Útil si uno no es accesible desde tu red. | `stooq,yahoo` |

### Si los precios no te funcionan

El precio es el único dato sin el cual la herramienta no puede opinar, así que
hay **dos proveedores** y se usa el primero que responda; la cita siempre nombra
al que realmente sirvió el dato. Stooq no es accesible desde todas las redes.
Si el diagnóstico te dice que uno falla y el otro no, fija el orden:

```
PRICE_PROVIDERS=yahoo,stooq
```

(esa línea va en tu `.env`, sin comillas ni `export`)

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
cd backend && ../.venv/bin/python -m pytest        # 266 tests
```

| Archivo | Qué cubre |
|---|---|
| `test_hard_rules.py` | Las cuatro reglas innegociables y la honestidad sobre datos viejos. |
| `test_engine.py` | Derivación de estrategia, indicadores, cartera, guardianes integrados. |
| `test_providers.py` | Los parsers de cada fuente contra payloads con la forma documentada. |
| `test_api.py` | La API completa, incluidas regresiones de fallos reales encontrados probando. |
| `test_suite_isolation.py` | Que la propia suite siga aislada de la configuración de quien la ejecuta. |
| `test_auth.py` | La contraseña, las sesiones, que **ninguna** ruta de datos responda sin ella, y que servir la interfaz no deje salir del directorio. |

Los tests **no leen tu `.env`** ni las variables de entorno de tu máquina
(`backend/conftest.py`). Un test que pasa en un ordenador y falla en otro por la
configuración personal de cada uno no mide el código, mide el ordenador.

**No tocan la red**: los proveedores se sustituyen por dobles deterministas y
fixtures. Eso prueba la lógica, no la disponibilidad — para la disponibilidad
está `diagnose.py`.

---

## Publicarla en internet, con contraseña

En tu ordenador la herramienta arranca **abierta**, y ahí está bien: nadie más
llega a `127.0.0.1`. En cuanto la pones en una dirección pública eso deja de ser
cierto, así que hay una capa de acceso. Sin ella, cualquiera con el enlace vería
tu cartera entera y podría borrarla.

Sigue siendo de **solo lectura frente al mercado**: publicarla no añade ninguna
ruta que envíe órdenes a un bróker. Lo que se protege son tus datos.

### 1. Pon tu contraseña

```bash
.venv/bin/python backend/set_password.py
```

Te la pide sin mostrarla en pantalla, calcula el hash y lo escribe en el `.env`
como `APP_PASSWORD_HASH`. La contraseña en claro **no se guarda en ninguna
parte** — ni en el archivo, ni en la base de datos, ni en los registros. Si la
olvidas, vuelve a ejecutar el script: no hay forma de recuperarla, solo de
sustituirla, y eso es a propósito.

Usa una larga. Un gestor de contraseñas y no volver a pensar en ella es mejor
que algo que puedas teclear de memoria.

### 2. Construye la imagen

```bash
docker build -t inversion-personal .
```

Compila la interfaz y la sirve **desde el mismo proceso** que la API. Eso no es
un detalle de comodidad: con un solo origen, la cookie de sesión nunca cruza
dominios y `SameSite=Strict` puede protegerla de verdad.

### 3. Arráncala

```bash
docker run -d -p 8000:8000 \
  -v inversion_datos:/data \
  -e APP_PASSWORD_HASH='pbkdf2_sha256$...' \
  -e INVEST_CONTACT='tu-email@ejemplo.com' \
  inversion-personal
```

### Tres cosas que hay que hacer bien

**HTTPS, no negociable.** La cookie de sesión viaja marcada `Secure`, así que
por HTTP normal el navegador ni la envía y no podrás entrar. Eso es la
protección funcionando, no un fallo: sin HTTPS tu contraseña viajaría legible
por la red. Cualquier plataforma con certificado automático sirve (Fly.io,
Railway, Render, Caddy o Nginx delante). Solo para probar en local existe
`APP_INSECURE_COOKIE=1`, que **nunca** debe ponerse en internet.

**Un volumen de verdad para la base de datos.** El disco de un contenedor es
efímero: sin el `-v`, el siguiente despliegue borra tu cartera, tu bitácora y
tus tesis. Si tu plataforma ofrece disco persistente, móntalo en `/data`.

**El hash como variable de la plataforma, no en el repositorio.** El `.env` está
en `.gitignore` y así debe seguir. En Fly.io es `fly secrets set`, en Railway y
Render el panel de variables de entorno.

### Qué protege y qué no

| | |
|---|---|
| Contraseña | PBKDF2-HMAC-SHA256, 600 000 iteraciones, sal por contraseña. |
| Sesiones | Token de 256 bits, guardado **hasheado**; revocable al instante, caduca a las 12 h. |
| Cookie | `HttpOnly` (invisible para JavaScript), `SameSite=Strict`, `Secure`. |
| Fuerza bruta | Bloqueo temporal por IP tras varios intentos fallidos. |
| Rutas de datos | Todas exigen sesión. Un test recorre la lista y falla si alguna responde sin ella. |

Lo que **no** hace: no hay segundo factor, ni usuarios múltiples, ni recuperar
la contraseña por email. Es una herramienta de una sola persona y añadir eso
sería complejidad que no te sirve.

Si sospechas que alguien más entró, **Salir de todas las sesiones** invalida
todos los tokens a la vez, estén en el dispositivo que estén.

Antes de publicar, exporta tus datos desde **Ajustes**. Son tuyos y conviene
tener una copia fuera del servidor.

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

```bash
python main.py                # descarga el índice del año en curso
python main.py --year 2025    # otro año
```

**Qué te da y qué no.** El ZIP anual del Clerk contiene el **índice de
presentaciones**: quién presentó un Periodic Transaction Report y cuándo. **No
contiene las transacciones.** El ticker y el importe están en el PDF de cada
PTR, y esos PDFs son con frecuencia escaneos. Así que la fuente oficial gratuita
te dice *quién* movió algo y *cuándo lo declaró*, pero no *qué compró*; se
guarda el enlace al PDF para que lo abras tú. Para obtener tickers
automáticamente hace falta procesar los PDFs o usar un agregador de terceros
(`connectors/aggregator.py` es el punto de extensión; revisa sus términos de uso
antes de activarlo).

**No influye en ninguna recomendación**, y no es un descuido. Los PTR pueden
presentarse hasta ~45 días después de la operación: describen el pasado, a veces
un pasado de mes y medio. Para cuando tú lo ves, el mercado hace mucho que lo
sabe. Es contexto de color, nunca una señal de compra o venta.

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
