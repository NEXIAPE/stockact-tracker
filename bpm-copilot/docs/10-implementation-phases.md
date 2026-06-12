# 10 · Plan de implementación por fases

## Fase 0 — Descubrimiento ✅ (completada)
Cuestionamiento de supuestos, decisiones de producto, definición de principios
(ver [entregable 0](./00-discovery.md)).

## Fase 1 — MVP: Transcripción → Minuta + artefactos ✅ (este entregable)
- Stack, modelo de datos, arquitectura hexagonal.
- CRUD Proyecto / Proceso / Reunión.
- Pipeline de ingesta con IA agnóstica (Claude/Ollama/Mock).
- Minuta + acuerdos/pendientes/decisiones/riesgos.
- Propuestas de cambio BPMN + aprobación (human-in-the-loop).
- Versionado del Proceso Vivo + exportación Mermaid.
- Dashboard de proceso + historial.

**Hito:** un analista recorre el flujo completo sin tocar la terminal.

## Fase 2 — Edición y madurez del artefacto
- Edición/cierre manual de pendientes, decisiones, riesgos.
- Render visual del BPMN (Mermaid en cliente) + diff visual de propuestas.
- Catálogo de personas/roles (RACI) → pendientes con responsables reales.
- **Generación de procedimiento** desde el proceso consolidado (estructura del
  brief: objetivo, alcance, roles, definiciones, políticas, desarrollo,
  indicadores, riesgos, anexos).
- Importación de transcripción desde archivo (.txt / .vtt / .docx).

**Hito:** la app reemplaza a las minutas en Word y al Excel de pendientes.

## Fase 3 — Escala de contenido e inteligencia
- Chunking + map-reduce para reuniones largas.
- Reconciliación de conflictos entre reuniones.
- Búsqueda semántica (RAG) sobre el histórico del proceso.
- Export BPMN-XML / PlantUML; evaluación de import/export Bizagi.
- Linter de buenas prácticas BPMN.

**Hito:** "copiloto" real que responde preguntas sobre el proceso vivo.

## Fase 4 — Producto / SaaS
- Autenticación (NextAuth) + organizaciones + RBAC.
- Migración a Postgres + `tenantId` (multi-tenant).
- Procesamiento asíncrono en cola (workers).
- Almacenamiento de objetos para transcripciones y exports.
- Facturación y planes.

**Hito:** equipos de Process Designers trabajando en paralelo; base para SaaS.

## Gestión de riesgos del proyecto

| Riesgo | Mitigación |
|---|---|
| Calidad de extracción variable según LLM | Contrato Zod + adaptador conmutable + reproceso desde `rawExtraction`. |
| Coste de API si crece el uso | Default conmutable a Ollama/mock; una sola llamada por reunión. |
| Confianza en cambios automáticos | Human-in-the-loop obligatorio; nada se aplica sin aprobación. |
| Lock-in de proveedor | Arquitectura hexagonal; dominio sin dependencias externas. |
| Crecimiento del esquema | Prisma + migraciones; SQLite→Postgres sin reescritura. |
