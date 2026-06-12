import type { BpmnModel } from "@/core/domain/bpmn";
import { toMermaid } from "@/core/domain/mermaid";
import { EmptyState } from "./ui";

/**
 * Visualización del BPMN vigente sin dependencias de cliente:
 *  - Lista estructurada de elementos (eventos, actividades por rol, gateways).
 *  - Bloque Mermaid copiable (para pegar en cualquier visor Mermaid).
 */
export function BpmnView({ model }: { model: BpmnModel }) {
  const total = model.events.length + model.activities.length + model.gateways.length;
  if (total === 0) {
    return <EmptyState title="Sin BPMN aún" hint="Procesa una reunión y aprueba propuestas para construir el flujo." />;
  }

  const byRole = new Map<string, typeof model.activities>();
  for (const a of model.activities) {
    const k = a.role ?? "Sin rol asignado";
    byRole.set(k, [...(byRole.get(k) ?? []), a]);
  }

  return (
    <div className="grid gap-4">
      <div className="grid gap-2 sm:grid-cols-3">
        <Stat label="Eventos" value={model.events.length} />
        <Stat label="Actividades" value={model.activities.length} />
        <Stat label="Gateways" value={model.gateways.length} />
      </div>

      <div className="grid gap-3">
        {[...byRole.entries()].map(([role, acts]) => (
          <div key={role} className="rounded-lg border border-slate-200 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-brand-700">{role}</p>
            <ul className="grid gap-1.5">
              {acts.map((a) => (
                <li key={a.id} className="flex items-center gap-2 text-sm">
                  <span className="grid h-5 w-5 place-items-center rounded bg-brand-50 text-[10px] text-brand-700">▢</span>
                  <span className="text-slate-700">{a.name}</span>
                  {a.system && <span className="badge bg-slate-100 text-slate-500">{a.system}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
          Código Mermaid (exportable)
        </summary>
        <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          <code>{toMermaid(model)}</code>
        </pre>
      </details>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 text-center">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}
