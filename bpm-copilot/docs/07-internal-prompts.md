# 7 · Prompts internos

Implementación: [`src/core/ai/prompts.ts`](../src/core/ai/prompts.ts).

## Estrategia
Un **único prompt de extracción estructurada** por reunión que:
1. Recibe la transcripción.
2. Recibe el **contexto del Proceso Vivo**: BPMN vigente + resúmenes de reuniones
   previas (memoria). Esto cumple el requisito "no tratar cada reunión como
   información aislada".
3. Devuelve **JSON estricto** validado por `MeetingExtractionSchema` (Zod). Si el
   modelo se desvía, Zod lo rechaza y el adaptador puede reintentar.

## System prompt (resumen)
Define el rol (Consultor BPM Senior) y los principios:
- Enriquecer, no reemplazar (se entrega el BPMN vigente para detectar *deltas*).
- Ser conservador: no inventar lo que no está en la transcripción.
- Distinguir **acuerdo vs decisión vs pendiente vs riesgo** (con definiciones).
- Para BPMN, identificar eventos, actividades (rol + sistema), gateways, roles,
  sistemas, entradas y salidas.
- Salida **exclusivamente JSON** conforme al contrato.

## User prompt (estructura)
```
PROCESO: <nombre>
OBJETIVO: <objetivo>
MEMORIA DEL PROCESO (resúmenes previos): ...
BPMN VIGENTE (modelo canónico): <JSON>
=== TRANSCRIPCIÓN ===
<texto>
=== FIN ===
Instrucción: compara contra el BPMN vigente y propón SOLO deltas.
```

## Contrato de salida (`MeetingExtraction`)
```jsonc
{
  "summary": "minuta narrativa breve",
  "participants": ["..."],
  "agreements":  [{ "text": "..." }],
  "actionItems": [{ "description", "owner?", "dueDate?" }],
  "decisions":   [{ "statement", "rationale?", "owner?" }],
  "risks":       [{ "description", "impact", "likelihood", "mitigation?" }],
  "bpmnChanges": [{ "action": "add|update|remove", "title", "detail?",
                    "fragment": { /* BPMN parcial */ } }]
}
```

## Por qué un solo prompt (y no una cadena de agentes)
- **Coste y latencia**: una llamada por reunión vs. varias. Importa por el
  requisito de minimizar consumo de API.
- **Coherencia**: el modelo ve todo el contexto a la vez y correlaciona
  (un riesgo mencionado junto a una decisión).
- **Evolución**: si una sección crece (p.ej. BPMN complejo), se puede separar en
  un segundo prompt especializado sin tocar el resto del pipeline.

## Buenas prácticas aplicadas
- **Salida estructurada validada** (Zod) en lugar de parsear texto libre.
- **Few-shot implícito** vía definiciones precisas en el system prompt.
- **Tolerancia a `code fences`**: `parseJsonLoose` limpia ```json ... ```.
- **Temperatura baja** (Ollama) para extracción determinista.
- **Idempotencia**: el `transcriptHash` evita reprocesar contenido idéntico.

## Futuras mejoras
- Prompt de **reconciliación de conflictos** entre reuniones.
- Prompt de **generación de procedimiento** desde el proceso consolidado.
- **Citas exactas** (offsets en la transcripción) para cada artefacto extraído.
