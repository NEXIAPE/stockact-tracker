# 8 · Estrategia de almacenamiento

## Principio: local-first, evolutivo

| Dato | Hoy (MVP) | SaaS (futuro) |
|---|---|---|
| Entidades estructuradas | SQLite (`prisma/dev.db`) | Postgres gestionado (Neon/Supabase) |
| Transcripciones | Campo `text` en `Meeting` | Object storage (S3/R2) + referencia |
| Modelo BPMN | JSON en `ProcessVersion.bpmnModel` | igual (JSONB en Postgres) |
| Salida cruda IA | JSON en `Meeting.rawExtraction` | igual |
| Documentos generados | JSON en `Procedure.sections` | + exportación a archivo |

## Por qué SQLite primero
- **Cero infraestructura**: un archivo, sin servidor de base de datos.
- **Privacidad**: los datos no salen de tu máquina (salvo la transcripción si
  usas el adaptador Claude).
- **Portabilidad**: respaldar = copiar `dev.db`.
- **Migración trivial**: cambiar `provider` a `postgresql` + `DATABASE_URL`.
  El esquema Prisma es el mismo; solo enums/JSON se afinan.

## Versionado e inmutabilidad
- `ProcessVersion` es **append-only**: nunca se actualiza una versión existente;
  aprobar un cambio crea `version + 1`. Esto da un historial BPMN reconstruible.
- `ChangeLogEntry` es el registro append-only de toda mutación relevante.
- `rawExtraction` se guarda para **auditoría y reproceso** (poder re-derivar
  artefactos si mejora el prompt, sin re-llamar al LLM).

## Idempotencia
- `transcriptHash` (SHA-256 del texto) permite detectar reprocesos de contenido
  idéntico.
- El pipeline **limpia los artefactos previos de la reunión** (por
  `sourceMeetingId`) antes de reinsertar → reprocesar no duplica.

## Respaldo y exportación
- **Backup MVP**: copiar `prisma/dev.db`.
- **Export BPMN**: Mermaid hoy; BPMN-XML / PlantUML en backlog.
- **Export documental**: el procedimiento (JSON `sections`) se renderiza a
  Markdown/PDF en fase posterior.

## Consideración de confidencialidad
Las transcripciones pueden contener información sensible. Por eso la elección de
adaptador de IA es también una **decisión de gobierno del dato**:
- `mock` / `ollama` → **ningún dato sale** del equipo.
- `claude` → la transcripción se envía a la API de Anthropic (documentado en el
  `.env.example` y el README).
