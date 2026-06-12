# 11 · Guía de instalación local (tu PC)

Dos caminos. Elige uno. Ambos dejan la app en **http://localhost:3000** con tu
base de datos privada en tu máquina (nada se sube a la nube).

---

## Camino A — Con Node.js (recomendado para desarrollar/ajustar)

**Requisito:** [Node.js 20 o superior](https://nodejs.org) instalado.
Comprueba con: `node -v`

```bash
# 1) Clonar el repo y entrar a la carpeta del proyecto
git clone <URL-del-repo>
cd stockact-tracker/bpm-copilot
git checkout claude/bpm-copilot-platform-xd8aja

# 2) Crear el archivo de configuración
cp .env.example .env

# 3) Instalar dependencias
npm install

# 4) Preparar la base de datos + datos de ejemplo (una sola vez)
npm run setup

# 5) Arrancar
npm run dev
```

Abre **http://localhost:3000**. Listo.

| Comando | Para qué |
|---|---|
| `npm run dev` | Arrancar la app (uso diario) |
| `npm run db:studio` | Ver/editar la base de datos visualmente |
| `npm run db:reset` | Borrar todo y volver a los datos de ejemplo |

---

## Camino B — Con Docker (casi un clic, sin instalar Node)

**Requisito:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado.

```bash
cd stockact-tracker/bpm-copilot
docker compose up
```

La primera vez tarda unos minutos (construye la imagen). Cuando veas
`Iniciando Copiloto BPM en http://localhost:3000`, abre esa dirección.

- **Detener:** `docker compose down` (los datos **se conservan**).
- **Actualizar tras cambios de código:** `docker compose up --build`.
- **Empezar de cero (borrar datos):** `docker compose down -v`.

> La base de datos vive en un volumen Docker llamado `bpm_data`, así que sobrevive
> a reinicios y actualizaciones de la app.

---

## Activar Claude (extracción real con IA)

Por defecto la app funciona **gratis** con un extractor heurístico (`mock`).
Para usar Claude y obtener calidad real (mejores artefactos, mejores
recomendaciones del consultor):

1. Consigue una API key en https://console.anthropic.com
2. Edita tu archivo `.env`:
   ```bash
   LLM_PROVIDER="claude"
   ANTHROPIC_API_KEY="sk-ant-..."
   ```
3. Reinicia (`npm run dev` o `docker compose up --build`).

> **Privacidad:** con `claude`, el **texto de la transcripción** se envía a la API
> de Anthropic para procesarse (no se almacena ahí; ver su política). Con `mock` o
> `ollama` (modelo local) **nada sale de tu equipo**.

---

## ¿Dónde están mis datos?

- **Camino A:** en el archivo `bpm-copilot/prisma/dev.db` (SQLite). Para respaldar,
  copia ese archivo. Para empezar limpio, bórralo y corre `npm run setup`.
- **Camino B:** en el volumen Docker `bpm_data`.

Todo (proyectos, procesos, transcripciones, minutas, BPMN, recomendaciones)
queda guardado ahí y persiste entre sesiones.

---

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `node: command not found` | Instala Node.js 20+ y reinicia la terminal. |
| El puerto 3000 está ocupado | Cierra lo que lo use, o `PORT=3001 npm run dev`. |
| La página sale sin estilos / 404 raro | Había un servidor viejo corriendo; ciérralo y vuelve a arrancar. |
| Quiero ver la base de datos | `npm run db:studio` abre un explorador visual. |
