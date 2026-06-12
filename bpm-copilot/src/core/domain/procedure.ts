/**
 * Generación de procedimientos a partir del proceso consolidado.
 *
 * Determinista (sin LLM): replica el formato corporativo (estilo Entel):
 *  - Cabecera de control: Código, Versión, Área, Fecha.
 *  - Tabla de roles/firmas desde los stakeholders del proyecto.
 *  - Matriz de desarrollo: N° | Responsable | Descripción | Registros.
 *  - Secciones estándar del brief (objetivo, alcance, definiciones, políticas,
 *    desarrollo, indicadores, riesgos, anexos).
 */
import type { BpmnModel } from "./bpmn";
import { toMermaid } from "./mermaid";

export interface ProcedureTable {
  headers: string[];
  rows: string[][];
}
export interface ProcedureSection {
  key: string;
  title: string;
  /** Contenido en Markdown (cuando no es tabla). */
  body?: string;
  /** Contenido tabular (Matriz de desarrollo, roles, control del documento). */
  table?: ProcedureTable;
}

export interface ProcedureStakeholder {
  name: string;
  role?: string | null;
  area?: string | null;
}
export interface ProcedureInput {
  processName: string;
  code?: string | null;
  area?: string | null;
  version: number;
  objective?: string | null;
  scope?: string | null;
  bpmn: BpmnModel;
  stakeholders: ProcedureStakeholder[];
  decisions: { statement: string; rationale?: string | null; owner?: string | null }[];
  risks: { description: string; impact: string; mitigation?: string | null }[];
}

export const PROCEDURE_SECTIONS = [
  "control",
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
  const today = new Date().toLocaleDateString("es", { year: "numeric", month: "2-digit", day: "2-digit" });

  // 0. Control del documento (cabecera)
  const control: ProcedureSection = {
    key: "control",
    title: "Control del documento",
    table: {
      headers: ["Campo", "Valor"],
      rows: [
        ["Código", input.code || "—"],
        ["Versión", String(input.version).padStart(2, "0")],
        ["Área", input.area || "—"],
        ["Proceso", input.processName],
        ["Fecha de generación", today],
      ],
    },
  };

  // 3. Roles y responsabilidades (desde stakeholders + roles BPMN no cubiertos)
  const stakeholderNames = new Set(input.stakeholders.map((s) => (s.role ?? "").toLowerCase()));
  const extraRoles = bpmn.roles.filter((r) => !stakeholderNames.has(r.toLowerCase()));
  const rolesTable: ProcedureTable = {
    headers: ["Nombre", "Cargo", "Área"],
    rows: [
      ...input.stakeholders.map((s) => [s.name, s.role || "—", s.area || "—"]),
      ...extraRoles.map((r) => ["—", r, "—"]),
    ],
  };
  if (rolesTable.rows.length === 0) rolesTable.rows.push(["—", "Sin stakeholders registrados", "—"]);

  // 6. Matriz de desarrollo: N° | Responsable | Descripción | Registros
  const orderedActivities = orderActivitiesByFlow(bpmn);
  const matriz: ProcedureTable = {
    headers: ["N°", "Responsable", "Descripción", "Registros"],
    rows: orderedActivities.length
      ? orderedActivities.map((a, i) => [
          String(i + 1),
          a.role || "—",
          a.name + (a.system ? ` (${a.system})` : ""),
          a.outputs.length ? a.outputs.join(", ") : "n/a",
        ])
      : [["—", "—", "El flujo aún no tiene actividades. Procesa reuniones y aprueba propuestas BPMN.", "—"]],
  };

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

  return [
    control,
    { key: "objetivo", title: "1. Objetivo", body: input.objective?.trim() || "_Por definir._" },
    { key: "alcance", title: "2. Alcance", body: input.scope?.trim() || "_Por definir._" },
    { key: "roles", title: "3. Roles y responsabilidades", table: rolesTable },
    { key: "definiciones", title: "4. Definiciones", body: bullet(definitions) },
    { key: "politicas", title: "5. Políticas", body: bullet(policies) },
    { key: "desarrollo", title: "6. Desarrollo del procedimiento (Matriz de desarrollo)", table: matriz },
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
    { key: "anexos", title: "9. Anexos", body: "**Flujograma (BPMN):**\n\n```mermaid\n" + toMermaid(bpmn) + "\n```" },
  ];
}

/** Render del procedimiento completo a Markdown (incluye tablas). */
export function procedureToMarkdown(processName: string, sections: ProcedureSection[]): string {
  const parts = [`# Procedimiento: ${processName}\n`];
  for (const s of sections) {
    parts.push(`## ${s.title}`);
    if (s.table) {
      parts.push(tableToMarkdown(s.table));
    } else if (s.body) {
      parts.push(s.body);
    }
  }
  return parts.join("\n\n");
}

function tableToMarkdown(t: ProcedureTable): string {
  const head = `| ${t.headers.join(" | ")} |`;
  const sep = `| ${t.headers.map(() => "---").join(" | ")} |`;
  const rows = t.rows.map((r) => `| ${r.map((c) => c.replace(/\n/g, " ")).join(" | ")} |`);
  return [head, sep, ...rows].join("\n");
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

  const ordered: BpmnModel["activities"] = [];
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
  for (const a of bpmn.activities) if (!seen.has(a.id) && activityIds.has(a.id)) ordered.push(a);
  return ordered;
}
