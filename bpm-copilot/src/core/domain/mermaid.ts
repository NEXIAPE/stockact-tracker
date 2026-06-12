/** Exporta un BpmnModel interno a Mermaid (flowchart) para visualización. */
import type { BpmnModel } from "./bpmn";

function sanitize(id: string): string {
  return id.replace(/[^a-zA-Z0-9_]/g, "_");
}
function esc(label: string): string {
  return label.replace(/"/g, "'").slice(0, 60);
}

export function toMermaid(model: BpmnModel): string {
  const lines: string[] = ["flowchart TD"];

  for (const e of model.events) {
    const id = sanitize(e.id);
    if (e.type === "start") lines.push(`  ${id}(["${esc(e.name)}"])`);
    else if (e.type === "end") lines.push(`  ${id}(["${esc(e.name)}"])`);
    else lines.push(`  ${id}("${esc(e.name)}")`);
  }
  for (const a of model.activities) {
    const role = a.role ? `<br/><i>${esc(a.role)}</i>` : "";
    lines.push(`  ${sanitize(a.id)}["${esc(a.name)}${role}"]`);
  }
  for (const g of model.gateways) {
    lines.push(`  ${sanitize(g.id)}{"${esc(g.name)}"}`);
  }
  for (const f of model.flows) {
    const label = f.condition ? `|${esc(f.condition)}|` : "";
    lines.push(`  ${sanitize(f.from)} -->${label} ${sanitize(f.to)}`);
  }

  if (model.events.length + model.activities.length === 0) {
    lines.push("  empty[/\"Sin elementos BPMN aún\"/]");
  }
  return lines.join("\n");
}
