# 2 · Modelo de datos

Fuente de verdad: [`prisma/schema.prisma`](../prisma/schema.prisma).
Base local: **SQLite** (migrable a Postgres sin cambios de dominio).

## Diagrama entidad-relación

```
Project 1───* Process 1───* Meeting
                 │              │
                 │              ├── Agreement *      (acuerdos por reunión)
                 │              └── (origen de) ─────┐
                 │                                   │
                 ├── ProcessVersion *  (snapshots BPMN versionados)
                 │      └── currentVersion (puntero a la vigente)
                 │                                   │
                 ├── ActionItem *  ◄─── sourceMeeting┤
                 ├── Decision   *  ◄─── sourceMeeting┤
                 ├── Risk       *  ◄─── sourceMeeting┤
                 ├── ChangeLogEntry * ◄─ sourceMeeting┤
                 ├── ChangeProposal * (pending/approved/rejected) ◄─ meeting
                 └── Procedure  *
```

## Entidades

### Project (Proyecto)
`name`, `sponsor`, `status` (active·on_hold·closed), `startDate`, `endDate`.

### Process (Proceso) — raíz del "Proceso Vivo"
`name`, `objective`, `scope`, `status` (discovery·design·validation·approved·
deployed), `currentVersionId` → puntero a la `ProcessVersion` vigente.

### ProcessVersion — snapshot BPMN canónico (inmutable)
`version` (entero incremental), `bpmnModel` (JSON, ver entregable #9),
`sourceMeetingId`, `createdById`. Único por `(processId, version)`.
**Nunca se modifica**: aprobar un cambio crea una versión nueva.

### Meeting (Reunión) — fuente principal de conocimiento
`date`, `participants` (JSON string[]), `transcript`, `transcriptHash`
(idempotencia), `summary`, `processState` (uploaded·processing·processed·error),
`rawExtraction` (salida cruda del LLM para auditoría/reproceso).

### Artefactos consolidados (a nivel de Proceso)
- **Agreement**: `text` (vive en la reunión).
- **ActionItem** (pendiente): `description`, `owner`, `status`, `dueDate`, `sourceMeeting`.
- **Decision**: `statement`, `rationale`, `owner`, `decidedAt`, `sourceMeeting`.
- **Risk**: `description`, `impact`, `likelihood`, `mitigation`, `status`, `sourceMeeting`.

### ChangeProposal — el corazón del human-in-the-loop
`target` (bpmn·action_item·decision·risk·process_meta·procedure), `action`
(add·update·remove), `title`, `detail`, `payload` (JSON estructurado del
cambio), `status` (pending·approved·rejected), `confidence`, `reviewedBy`.

### ChangeLogEntry — historial (qué, cuándo, quién, reunión origen)
`entity`, `action`, `summary`, `diff` (JSON antes/después), `requestedBy`,
`sourceMeeting`.

### Procedure (Procedimiento)
`version`, `sections` (JSON con la estructura configurable del entregable #4 del
brief: objetivo, alcance, roles, definiciones, políticas, desarrollo,
indicadores, riesgos, anexos).

## Decisiones de modelado

- **Enums como String**: SQLite no soporta enums nativos. Valores documentados
  en comentarios del schema; validados por Zod en el dominio. Migrar a enums de
  Postgres es trivial.
- **Listas como JSON**: `participants`, `bpmnModel`, `payload`, `sections`.
  Prisma soporta `Json` sobre SQLite. Para campos consultables/filtrables se usan
  tablas normalizadas (ActionItem, Decision, Risk).
- **`sourceMeetingId` en todo artefacto**: trazabilidad total (requisito del brief).
- **Borrado en cascada** desde Project/Process: limpieza coherente.
- **Multi-tenant futuro**: añadir `organizationId`/`tenantId` + índices; el
  dominio no cambia.
