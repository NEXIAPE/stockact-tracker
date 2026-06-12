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

### Prioridad alta (siguiente iteración)
1. **Edición manual de artefactos** (editar/cerrar pendientes, decisiones, riesgos).
2. **Render visual del BPMN** (Mermaid en cliente, no solo código).
3. **Catálogo de personas/roles** normalizado → mejores pendientes y RACI.
4. **Generación de procedimiento** desde el proceso consolidado (estructura del brief).

### Prioridad media
5. **Chunking + map-reduce** para transcripciones largas (>1h).
6. **Diff visual** de la propuesta BPMN (antes/después) antes de aprobar.
7. **Importar transcripción desde archivo** (.txt/.vtt/.docx de Teams).
8. **Exportar BPMN-XML y PlantUML** (además de Mermaid).

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
