# 9 · Diseño BPMN interno

Implementación: [`src/core/domain/bpmn.ts`](../src/core/domain/bpmn.ts),
[`bpmn-merge.ts`](../src/core/domain/bpmn-merge.ts),
[`mermaid.ts`](../src/core/domain/mermaid.ts).

## Filosofía
Una **representación propia simplificada**, no paridad BPMN 2.0. Suficiente para
razonar, versionar y exportar. Se construye *antes* de integrar con Bizagi.

## Modelo canónico (`BpmnModel`)

```ts
{
  events:      [{ id, type: "start"|"end"|"intermediate", name }],
  activities:  [{ id, name, type, role?, system?, inputs[], outputs[] }],
  gateways:    [{ id, name, type: "exclusive"|"parallel"|"inclusive"|"event_based" }],
  flows:       [{ id, from, to, condition? }],
  roles:       string[],
  systems:     string[],
  dataObjects: string[]
}
```

Cubre los elementos que el brief pide identificar automáticamente:
**eventos, actividades, gateways, roles, sistemas, entradas y salidas**.

## Identificación automática
El LLM (vía prompt) mapea el lenguaje natural de la transcripción a este modelo:
- Verbos de proceso → **actividades** (con `role` = quién la ejecuta, `system` =
  dónde).
- "empieza cuando…" / "termina cuando…" → **eventos** start/end.
- "si… entonces… si no…" → **gateways** exclusivos + flujos condicionales.
- Entradas/salidas de cada actividad → `inputs`/`outputs`.

## Versionado y merge (Proceso Vivo)
1. El BPMN vigente vive en `Process.currentVersion.bpmnModel`.
2. Cada reunión produce **fragmentos** (deltas) como `ChangeProposal`.
3. Al **aprobar**, `applyFragment(current, action, fragment)` produce un modelo
   nuevo:
   - `add` / `update` → *upsert* por `id` (elementos, flujos, roles, sistemas).
   - `remove` → elimina nodos y los flujos que los referencian.
4. Se crea una **`ProcessVersion` nueva** (inmutable) y se actualiza el puntero.

```
BPMN v1  ──(propuesta aprobada)──►  applyFragment  ──►  BPMN v2  ──► …
```

## Exportación
- **Mermaid** (✅): `toMermaid(model)` genera un `flowchart TD` con eventos,
  actividades (con rol), gateways y flujos etiquetados. Pegable en cualquier
  visor Mermaid.
- **BPMN-XML** (backlog): mapear a `<bpmn:process>` con `bpmndi` para layout.
- **PlantUML** (backlog): generar `@startuml` activity diagram.

## Decisiones de diseño
- **Upsert por `id`** en vez de reemplazo total → preserva trabajo previo
  (principio "enriquecer, no pisar").
- **Validación Zod** del modelo en cada merge → un fragmento mal formado no
  corrompe el grafo vigente.
- **Roles/sistemas como listas de strings** en el MVP → simple; se normalizarán
  a entidades cuando llegue el catálogo de personas (RACI).

## Limitaciones conocidas (MVP)
- Sin *layout* automático (posiciones x/y): se delega al visor Mermaid.
- Sin validación de buenas prácticas BPMN aún (p.ej. "todo gateway que abre,
  cierra"). Es un *linter* BPMN candidato a fase posterior.
- Sub-procesos representados como actividad `subprocess` sin expansión anidada.
