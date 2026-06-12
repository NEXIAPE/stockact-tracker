/**
 * Generación de procedimientos a partir del proceso consolidado.
 *
 * Determinista (sin LLM): ensambla la estructura estándar del brief desde los
 * artefactos vivos (BPMN vigente, decisiones, riesgos). Estructura configurable
 * vía PROCEDURE_SECTIONS.
 */
import type { BpmnModel } from "./bpmn";
import { toMermaid } from "./mermaid";

export interface ProcedureSection {
  key: string;
  title: string;
  /** Contenido en Markdown. */
  body: string;
}

export interface ProcedureInput {
  processName: string;
  objective?: string | null;
  scope?: string | null;
  bpmn: BpmnModel;
  decisions: { statement: string; rationale?: string | null; owner?: string | null }[];
  risks: { description: string; impact: string; mitigation?: string | null }[];
}

/** Orden y títulos de las secciones (configurable). */
export const PROCEDURE_SECTIONS = [
  "objetivo",
  "alcance",
  "roles",
  "definiciones",
  "politicas",
  "desarrollo",
  "indicadores",
  "riesgos",
  "anexos",
] as const;

function bullet(items: string[]): string {
  return items.length ? items.map((i) => `- ${i}`).join("\n") : "_Sin elementos registrados._";
}

export function buildProcedure(input: ProcedureInput): ProcedureSection[] {
  const { bpmn } = input;

  // Desarrollo: actividades en orden de flujo cuando es posible.
  const orderedActivities = orderActivitiesByFlow(bpmn);
  const development = orderedActivities.length
    ? orderedActivities
        .map((a, i) => {
          const who = a.role ? ` **(${a.role})**` : "";
          const sys = a.system ? ` _[${a.system}]_` : "";
          const io =
            a.inputs.length || a.outputs.length
              ? ` — entradas: ${a.inputs.join(", ") || "—"}; salidas: ${a.outputs.join(", ") || "—"}`
              : "";
          return `${i + 1}. ${a.name}${who}${sys}${io}`;
        })
        .join("\n")
    : "_El flujo aún no tiene actividades. Procesa reuniones y aprueba propuestas BPMN._";

  const definitions = [
    ...bpmn.systems.map((s) => `**${s}**: sistema de información utilizado en el proceso.`),
    ...bpmn.dataObjects.map((d) => `**${d}**: objeto/documento de datos del proceso.`),
  ];

  const policies = input.decisions.map(
    (d) => `${d.statement}${d.rationale ? ` (justificación: ${d.rationale})` : ""}${d.owner ? ` — ${d.owner}` : ""}`
  );

  const risksBody = input.risks.length
    ? input.risks
        .map((r) => `- **${r.description}** · impacto: ${r.impact}${r.mitigation ? ` · mitigación: ${r.mitigation}` : ""}`)
        .join("\n")
    : "_Sin riesgos registrados._";

  const sections: ProcedureSection[] = [
    { key: "objetivo", title: "1. Objetivo", body: input.objective?.trim() || "_Por definir._" },
    { key: "alcance", title: "2. Alcance", body: input.scope?.trim() || "_Por definir._" },
    { key: "roles", title: "3. Roles y responsabilidades", body: bullet(bpmn.roles) },
    { key: "definiciones", title: "4. Definiciones", body: bullet(definitions.length ? definitions : []) },
    { key: "politicas", title: "5. Políticas", body: bullet(policies) },
    { key: "desarrollo", title: "6. Desarrollo del procedimiento", body: development },
    {
      key: "indicadores",
      title: "7. Indicadores",
      body: bullet([
        "Tiempo de ciclo del proceso (lead time).",
        "% de casos completados sin retrabajo.",
        "Cumplimiento de SLA por actividad.",
      ]),
    },
    { key: "riesgos", title: "8. Riesgos", body: risksBody },
    { key: "anexos", title: "9. Anexos", body: "**Diagrama BPMN (Mermaid):**\n\n```mermaid\n" + toMermaid(bpmn) + "\n```" },
  ];

  return sections;
}

/** Render del procedimiento completo a Markdown. */
export function procedureToMarkdown(processName: string, sections: ProcedureSection[]): string {
  const header = `# Procedimiento: ${processName}\n`;
  return header + "\n" + sections.map((s) => `## ${s.title}\n\n${s.body}`).join("\n\n");
}

/** Ordena actividades siguiendo los flujos desde el evento de inicio (best-effort). */
function orderActivitiesByFlow(bpmn: BpmnModel): BpmnModel["activities"] {
  const activityIds = new Set(bpmn.activities.map((a) => a.id));
  if (bpmn.flows.length === 0) return bpmn.activities;

  const start = bpmn.events.find((e) => e.type === "start");
  const adjacency = new Map<string, string[]>();
  for (const f of bpmn.flows) {
    adjacency.set(f.from, [...(adjacency.get(f.from) ?? []), f.to]);
  }

  const ordered: typeof bpmn.activities = [];
  const seen = new Set<string>();
  const queue: string[] = start ? [start.id] : bpmn.activities.map((a) => a.id);

  while (queue.length) {
    const id = queue.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    const act = bpmn.activities.find((a) => a.id === id);
    if (act) ordered.push(act);
    for (const next of adjacency.get(id) ?? []) if (!seen.has(next)) queue.push(next);
  }

  // Añade actividades no alcanzadas por el flujo.
  for (const a of bpmn.activities) if (!seen.has(a.id) && activityIds.has(a.id)) ordered.push(a);
  return ordered;
}
