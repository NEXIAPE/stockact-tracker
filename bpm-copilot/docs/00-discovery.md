# 0 · Descubrimiento y supuestos cuestionados

> Fase previa al código. Aquí se documenta el cuestionamiento crítico del brief
> y las decisiones de producto que dan forma al MVP.

## Las 4 tensiones de diseño detectadas

### 1. "Copiloto IA" vs. "evitar APIs pagadas permanentes"
**Tensión:** todo el valor (extraer artefactos de transcripciones, mantener un
proceso vivo) es trabajo de un LLM, pero se pide evitar coste recurrente de API.

**Resolución:** arquitectura **agnóstica de IA** (puerto/adaptador hexagonal).
El dominio no conoce al proveedor. El MVP trae 3 adaptadores:
- `claude` (default, mejor calidad, tu suscripción),
- `ollama` (local, gratis),
- `mock` (heurístico, cero coste, para demos/CI/offline).

El coste pasa a ser una **decisión de despliegue**, no de arquitectura.

### 2. "Mantener BPMN automáticamente" es peligroso
**Supuesto derribado:** que la IA reescriba el diagrama vigente en cada reunión.
Esto destruye trabajo válido y erosiona la confianza.

**Resolución (principio no negociable):** **human-in-the-loop**. El sistema
*propone diffs* (`ChangeProposal`), el humano aprueba/rechaza, y cada aprobación
genera una nueva versión inmutable. Esto, además, *es* el "historial de cambios"
bien hecho (qué, cuándo, quién, reunión origen).

### 3. "Proceso Vivo" = estado versionado, no acumulación de minutas
**Insight:** el núcleo técnico no son las reuniones, es un **modelo canónico del
proceso versionado**. Las reuniones son la fuente de eventos; el "Proceso
Vigente" (`ProcessVersion`) es la proyección. Patrón: event-sourcing ligero.
Esto garantiza que "cada transcripción enriquece el conocimiento" en vez de
pisarlo.

### 4. "Extremadamente simple" ≠ pocas tablas
**Supuesto derribado:** simplificar la UI obligando a un modelo pobre, o
perseguir paridad BPMN 2.0 completa desde el día 1.

**Resolución:** UI minimalista (Proyecto → Proceso → Reunión) sobre un modelo
rico. BPMN propio **simplificado** que luego *exporta* a Mermaid / BPMN-XML /
PlantUML. No se persigue Bizagi en v1.

## Decisiones del usuario (validadas antes de codificar)

| Tema | Decisión |
|---|---|
| Motor IA | Agnóstico, **default Claude** |
| Stack | **Next.js + TS + Prisma + SQLite** |
| Ubicación | Subcarpeta `bpm-copilot/` en el repo existente |
| Foco MVP | **Transcripción → Minuta + artefactos consolidados** |

## Supuestos que aún conviene validar (próximas iteraciones)

1. **Idioma de las transcripciones**: se asume español (Teams). Multi-idioma es
   trivial de añadir en el prompt.
2. **Volumen de transcripción**: se asume que cabe en una ventana de contexto.
   Para reuniones de >2h habrá que *chunkear* + map-reduce (ver fase 3).
3. **Identidad de participantes**: hoy texto libre. Un catálogo de personas/roles
   normalizado mejora pendientes y RACI (fase 2).
4. **Conflictos entre reuniones**: si dos reuniones se contradicen, hoy ambas
   generan propuestas y el humano decide. Un motor de reconciliación explícito
   es trabajo futuro.
5. **Confidencialidad**: transcripciones pueden ser sensibles. `mock`/`ollama`
   permiten cero salida de datos; con `claude` se envían a la API. Documentado.
