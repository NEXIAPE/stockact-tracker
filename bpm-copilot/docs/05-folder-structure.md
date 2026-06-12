# 5 · Estructura de carpetas

```
bpm-copilot/
├── docs/                          # Entregables de diseño (0–10)
├── prisma/
│   ├── schema.prisma              # Modelo de datos (fuente de verdad)
│   ├── seed.ts                    # Datos de ejemplo
│   └── dev.db                     # SQLite (gitignored)
├── scripts/
│   └── verify-ingest.ts           # Test E2E del pipeline (offline)
├── src/
│   ├── app/                       # Next.js App Router (UI + Server Actions)
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   ├── page.tsx               # Proyectos
│   │   ├── actions.ts             # Server Actions (capa de aplicación)
│   │   ├── projects/[projectId]/page.tsx
│   │   ├── processes/[processId]/page.tsx
│   │   └── meetings/[meetingId]/page.tsx
│   ├── components/
│   │   ├── ui.tsx                 # Badges, breadcrumbs, empty states
│   │   └── BpmnView.tsx           # Visualización BPMN + Mermaid
│   ├── core/                      # ◄ NÚCLEO DE DOMINIO (puro, sin framework)
│   │   ├── domain/
│   │   │   ├── bpmn.ts            # Tipos + Zod del modelo BPMN interno
│   │   │   ├── extraction.ts      # Contrato de salida del LLM
│   │   │   ├── bpmn-merge.ts      # Aplicar deltas → nuevo modelo
│   │   │   └── mermaid.ts         # Exportador a Mermaid
│   │   ├── ai/                    # ◄ PUERTO + ADAPTADORES DE IA
│   │   │   ├── port.ts            # Interfaz LlmPort
│   │   │   ├── prompts.ts         # Prompts internos
│   │   │   ├── json.ts            # Parseo tolerante de JSON
│   │   │   ├── factory.ts         # Selección por LLM_PROVIDER
│   │   │   └── adapters/
│   │   │       ├── claude.ts
│   │   │       ├── ollama.ts
│   │   │       └── mock.ts
│   │   └── ingest/                # ◄ CASOS DE USO
│   │       ├── pipeline.ts        # Procesar reunión
│   │       └── proposals.ts       # Aprobar/rechazar → versionar BPMN
│   └── lib/
│       └── db.ts                  # Singleton de Prisma
├── .env.example
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json                  # alias @/* → src/*
└── package.json
```

## Reglas de dependencia (importante)

```
app/ ──► core/ ──► (nada externo salvo Zod / Prisma types)
  │         ▲
  └─► lib/db (Prisma)
```

- `src/core/**` **no importa** de `src/app/**` ni de React. Es portable a una API
  REST, un CLI o un worker sin cambios.
- Los adaptadores de IA son la **única** frontera con servicios externos.
- `src/app/actions.ts` es la capa de aplicación: orquesta el dominio y la
  persistencia; no contiene reglas de negocio.
