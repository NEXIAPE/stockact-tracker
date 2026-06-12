# 1 · Arquitectura de solución

## Visión general

Arquitectura **hexagonal (puertos y adaptadores)** sobre Next.js, con un núcleo
de dominio puro desacoplado del framework y del proveedor de IA.

```
┌─────────────────────────────────────────────────────────────┐
│                        UI (App Router)                       │
│   Proyectos → Procesos → Reuniones · Server Components        │
└───────────────┬──────────────────────────┬──────────────────┘
                │ Server Actions            │ (render)
┌───────────────▼──────────────────────────▼──────────────────┐
│                    Capa de aplicación                        │
│   src/app/actions.ts · orquesta casos de uso                 │
└───────────────┬──────────────────────────┬──────────────────┘
                │                           │
┌───────────────▼─────────────┐  ┌──────────▼──────────────────┐
│       Núcleo de dominio      │  │     Puerto de IA (LlmPort)  │
│  src/core/domain  · puro     │  │  src/core/ai/port.ts        │
│  - bpmn, extraction          │  │      ▲        ▲        ▲     │
│  - bpmn-merge, mermaid       │  │   Claude   Ollama    Mock   │
│  src/core/ingest · pipeline  │  │  (adaptadores)              │
└───────────────┬──────────────┘  └─────────────────────────────┘
                │ Prisma (puerto de persistencia)
┌───────────────▼──────────────────────────────────────────────┐
│                  SQLite (local-first) → Postgres (SaaS)       │
└───────────────────────────────────────────────────────────────┘
```

## Capas

| Capa | Responsabilidad | Ubicación |
|---|---|---|
| **UI** | Render y formularios. Server Components por defecto. | `src/app/**` |
| **Aplicación** | Casos de uso (crear proyecto, procesar reunión, aprobar propuesta). | `src/app/actions.ts` |
| **Dominio** | Reglas puras: BPMN, merge, extracción, exportación. Sin I/O. | `src/core/domain`, `src/core/ingest` |
| **Puertos** | Interfaces: `LlmPort` (IA), Prisma (persistencia). | `src/core/ai/port.ts`, `src/lib/db.ts` |
| **Adaptadores** | Implementaciones concretas intercambiables. | `src/core/ai/adapters/**` |

## Flujo clave — procesar una reunión

```
Usuario sube transcripción
        │
        ▼
processMeetingAction (Server Action)
        │
        ▼
processMeeting()  ──►  carga contexto del Proceso Vivo
        │              (BPMN vigente + resúmenes previos)
        ▼
getLlm().extractFromTranscript()  ──►  MeetingExtraction (Zod-validado)
        │
        ├─► persiste minuta (summary, participantes)
        ├─► persiste acuerdos / pendientes / decisiones / riesgos
        ├─► crea ChangeProposal[] (BPMN, estado=pending)
        └─► registra ChangeLogEntry
        │
        ▼
Humano revisa propuestas ──► approveProposal() ──► nueva ProcessVersion (BPMN v+1)
```

## Por qué Server Actions (y no una API REST separada)

- Menos piezas para el MVP: un solo despliegue, sin capa HTTP intermedia.
- Type-safety extremo a extremo (sin contratos duplicados).
- La frontera de dominio (`src/core`) ya está aislada: extraer una API REST o
  workers asíncronos en la fase SaaS es mecánico, no un rediseño.

## Evolución a SaaS (sin reescribir el dominio)

| Aspecto | MVP (hoy) | SaaS (futuro) |
|---|---|---|
| Persistencia | SQLite | Postgres + `tenantId` en cada tabla |
| IA | síncrona en la action | cola (BullMQ/QStash) + workers |
| Auth | usuario único | NextAuth + RBAC + organizaciones |
| Archivos | texto en DB | almacenamiento de objetos (S3/R2) |
| Despliegue | local / un contenedor | Vercel + Neon/Supabase |

El núcleo (`src/core`) permanece intacto en todos los casos.
