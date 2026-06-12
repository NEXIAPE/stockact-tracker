# 3 · Roadmap MVP

## Rebanada vertical elegida
**Transcripción → Minuta + artefactos consolidados** (el corazón del copiloto).

## Estado del MVP (este entregable)

| Capacidad | Estado |
|---|---|
| CRUD Proyecto / Proceso / Reunión | ✅ Implementado |
| Subir transcripción | ✅ |
| Procesar transcripción (IA agnóstica) | ✅ Claude / Ollama / Mock |
| Generar minuta (resumen + participantes) | ✅ |
| Extraer acuerdos / pendientes / decisiones / riesgos | ✅ |
| Detectar cambios BPMN vs. versión vigente | ✅ (propuestas) |
| Aprobar/rechazar propuestas (human-in-the-loop) | ✅ |
| Versionado del BPMN (Proceso Vivo) | ✅ |
| Dashboard de proceso (BPMN, estado, pendientes, riesgos, decisiones, cambios) | ✅ |
| Exportar BPMN a Mermaid | ✅ |
| Historial de cambios | ✅ |
| Idempotencia de reproceso | ✅ |

## Backlog priorizado (post-MVP)

### Prioridad alta — Fase 2 ✅ (entregada)
1. ✅ **Edición manual de artefactos** (alta/cambio de estado/borrado de
   pendientes, decisiones, riesgos desde el dashboard).
2. ✅ **Render visual del BPMN** (Mermaid en cliente, no solo código).
3. ✅ **Stakeholders del proyecto** (nombre, cargo, área) detectados
   automáticamente desde las transcripciones y editables. Alimentan los roles
   del procedimiento. *(RACI completo: pendiente)*
4. ✅ **Generación de procedimiento** en **formato corporativo** (estilo Entel):
   Control del documento (código/versión/área), tabla de Roles desde
   stakeholders, **Matriz de desarrollo** (N°|Responsable|Descripción|Registros),
   definiciones, políticas, indicadores, riesgos y flujograma en anexos +
   export Markdown.
7. ✅ **Importar transcripción desde archivo** (.txt/.vtt/.srt de Teams).

### Consultor proactivo — Fase 3 ✅ (entregada)
- ✅ **Recomendaciones del consultor**: el sistema PROPONE, no solo transcribe.
  - **Linter determinista** (coste cero): controles faltantes, eventos BPMN
    ausentes, actividades sin responsable, gateways sin ruta de excepción,
    actividades desconectadas, falta de registros/evidencia, ausencia de riesgos.
  - **Recomendaciones por IA** en cada reunión + **auditoría IA bajo demanda**
    ("Auditar proceso") cuando el proveedor lo soporta.
  - Aceptar una recomendación la convierte en pendiente o riesgo; descartar la
    archiva (no reaparece).
- ✅ **Tipo de trabajo del proceso** (new · improvement · owner_definition ·
  normative) que **orienta** qué propone el consultor.

### Prioridad media
5. **Chunking + map-reduce** para transcripciones largas (>1h).
6. **Diff visual** de la propuesta BPMN (antes/después) antes de aprobar.
8. **Exportar BPMN-XML y PlantUML** (además de Mermaid).
9. **RACI completo** (matriz responsable/aprobador por actividad).
10. **Export del procedimiento a .docx** con plantilla corporativa.

### Prioridad baja / SaaS
9. Autenticación + multi-tenant + RBAC.
10. Procesamiento asíncrono en cola.
11. Búsqueda semántica sobre el histórico de reuniones (RAG).
12. Integración Bizagi (import/export).

## Criterios de "hecho" del MVP
- Un analista puede crear proyecto → proceso → subir transcripción → obtener
  minuta y artefactos → revisar y aprobar cambios BPMN → ver el proceso vivo
  versionado, **sin tocar la línea de comandos** tras el arranque.
- Funciona **sin coste** (mock) y mejora con Claude/Ollama **sin cambiar código**.
