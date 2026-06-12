# 4 · Diseño UX/UI

## Principio rector
**Simplicidad extrema.** Una jerarquía clara, una acción protagonista por
pantalla, cero configuración para empezar.

## Mapa de navegación

```
/                         Proyectos (lista + crear)
/projects/[id]            Proyecto → Procesos (lista + crear)
/processes/[id]           Proceso → Dashboard + Reuniones (crear)
/meetings/[id]            Reunión → Procesar + Minuta + Propuestas
```

Breadcrumbs persistentes: `Proyectos / Proyecto / Proceso / Reunión`.

## Pantallas

### Home — Proyectos
Layout de 2 columnas: lista de proyectos (izq) + formulario "Nuevo proyecto"
sticky (der). Cada tarjeta muestra estado, sponsor y nº de procesos.

### Proyecto
Lista de procesos con contadores (reuniones, pendientes, riesgos) + formulario
"Nuevo proceso".

### Proceso — Dashboard (pantalla central)
Cumple el requisito del brief "dentro de cada proceso visualizar":

```
┌───────────────────────────────┬──────────────────────┐
│  BPMN vigente (2/3 de ancho)   │  Estado del proceso  │
│  - stats: eventos/act/gateways │  - contadores        │
│  - actividades por rol         │  - alcance           │
│  - código Mermaid exportable   │                      │
├───────────────┬───────────────┬──────────────────────┤
│  Pendientes   │  Riesgos      │  Decisiones          │
│  abiertos     │               │                      │
├───────────────┴───────────────┴──────────────────────┤
│  Últimos cambios (historial)                          │
├───────────────────────────────────────────────────────┤
│  Reuniones (lista)            │  Nueva reunión (form) │
└───────────────────────────────────────────────────────┘
```

Banner de aviso si hay propuestas pendientes de revisar.
Selector de estado del proceso (discovery → … → deployed) en el encabezado.

### Reunión
- **Acción protagonista**: botón "Procesar transcripción" (o "Reprocesar").
- Transcripción (izq) + Minuta generada (der: resumen + participantes).
- 4 columnas de artefactos: Acuerdos · Pendientes · Decisiones · Riesgos.
- **Propuestas de cambio BPMN** con botones **Aprobar / Rechazar** por propuesta.

## Sistema visual
- **Tailwind** con paleta `brand` (azul) + grises slate.
- Componentes reutilizables: `card`, `btn`, `badge`, `StatusBadge`,
  `Breadcrumbs`, `EmptyState` (ver `src/components/ui.tsx`).
- Estados con color semántico (verde=ok, ámbar=pendiente/medio, rojo=alto/error).
- Estados vacíos con guía ("crea tu primer…").

## Decisiones UX
- **Server Components + formularios nativos**: cero JS de cliente para el CRUD →
  rápido, accesible, sin estados de carga complejos en el MVP.
- **Una fuente de verdad visible**: el dashboard del proceso reúne todo lo que
  hoy está disperso (Teams, correos, Excel, Bizagi).
- **Aprobación explícita**: el cambio BPMN nunca es silencioso; el usuario ve la
  propuesta y su justificación (cita de la transcripción) antes de aceptar.
