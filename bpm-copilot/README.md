# Copiloto BPM — Diseño de Procesos

> Fuente única de verdad para proyectos de procesos. Convierte transcripciones
> de reuniones en artefactos vivos (minuta, pendientes, decisiones, riesgos,
> BPMN) que se enriquecen reunión a reunión, con aprobación humana de cada cambio.

Este es el MVP del **"Copiloto de Diseño de Procesos BPM"**: una app web
local-first construida con visión de escalar a equipo y, eventualmente, SaaS.

---

## ⚡ Quickstart

```bash
cd bpm-copilot
cp .env.example .env          # ajusta LLM_PROVIDER / ANTHROPIC_API_KEY si quieres IA real
npm install
npm run db:push               # crea la base SQLite (prisma/dev.db)
npm run db:seed               # datos de ejemplo (proyecto + proceso + transcripción)
npm run dev                   # http://localhost:3000
```

Abre la reunión sembrada y pulsa **«Procesar transcripción»**: se genera la
minuta, se extraen acuerdos/pendientes/decisiones/riesgos y se proponen cambios
BPMN que puedes **aprobar o rechazar**.

> Sin `ANTHROPIC_API_KEY`, la app funciona igualmente con un **extractor
> heurístico (mock)** sin coste ni red — ideal para demos y CI. La calidad real
> llega al configurar Claude (o un modelo local con Ollama).

---

## 🧠 Motor de IA — arquitectura agnóstica

El dominio depende de un **puerto** (`src/core/ai/port.ts`), no de un proveedor.
Se elige por variable de entorno, con degradación elegante:

| `LLM_PROVIDER` | Adaptador | Coste | Notas |
|---|---|---|---|
| `claude` (default) | `ClaudeAdapter` | Por uso (tu suscripción) | Mejor calidad. Cae a `mock` si no hay API key. |
| `ollama` | `OllamaAdapter` | Gratis (local) | Requiere `ollama serve` + modelo instruct. |
| `mock` | `MockAdapter` | Cero | Heurístico, offline, determinista. |

Cambiar de proveedor **no toca el dominio**: es una decisión de despliegue.

---

## 🗂️ Comandos

| Comando | Descripción |
|---|---|
| `npm run dev` | Servidor de desarrollo |
| `npm run build` | Build de producción (incluye `prisma generate`) |
| `npm run db:push` | Sincroniza el esquema con SQLite |
| `npm run db:seed` | Carga datos de ejemplo |
| `npm run db:studio` | Explorador visual de la base (Prisma Studio) |
| `npm run typecheck` | Verifica tipos |
| `npx tsx scripts/verify-ingest.ts` | Test end-to-end del pipeline (offline) |

---

## 📐 Principios de diseño (no negociables)

1. **Proceso Vivo** — el proceso vigente es una *proyección versionada*; cada
   reunión aplica un *changeset*, no reemplaza el conocimiento.
2. **Human-in-the-loop** — ninguna reunión muta el BPMN directamente; genera
   *propuestas* que un humano aprueba. Cada aprobación crea una versión.
3. **Trazabilidad total** — todo artefacto referencia su reunión de origen.
4. **Agnóstico de IA** — puerto/adaptador; el coste es configuración, no diseño.
5. **Local-first → SaaS** — SQLite hoy, Postgres multi-tenant mañana, sin
   reescribir el dominio.

---

## 📚 Documentación de diseño (entregables)

Todos los entregables solicitados están en [`docs/`](./docs):

| # | Documento |
|---|---|
| 0 | [Descubrimiento y supuestos cuestionados](./docs/00-discovery.md) |
| 1 | [Arquitectura de solución](./docs/01-architecture.md) |
| 2 | [Modelo de datos](./docs/02-data-model.md) |
| 3 | [Roadmap MVP](./docs/03-roadmap-mvp.md) |
| 4 | [Diseño UX/UI](./docs/04-ux-ui.md) |
| 5 | [Estructura de carpetas](./docs/05-folder-structure.md) |
| 6 | [Stack tecnológico](./docs/06-tech-stack.md) |
| 7 | [Prompts internos](./docs/07-internal-prompts.md) |
| 8 | [Estrategia de almacenamiento](./docs/08-storage-strategy.md) |
| 9 | [Diseño BPMN interno](./docs/09-bpmn-internal-design.md) |
| 10 | [Plan de implementación por fases](./docs/10-implementation-phases.md) |

---

## 🛠️ Stack

Next.js 15 (App Router, Server Actions) · TypeScript · Prisma · SQLite ·
Tailwind CSS · Zod. Sin dependencias de APIs pagadas obligatorias.
