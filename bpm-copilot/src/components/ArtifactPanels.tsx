import {
  addActionItem,
  updateActionItem,
  deleteActionItem,
  addDecision,
  deleteDecision,
  addRisk,
  updateRisk,
  deleteRisk,
} from "@/app/actions";
import { StatusBadge, EmptyState, fmtDate } from "./ui";

type ActionItem = {
  id: string;
  description: string;
  owner: string | null;
  status: string;
  dueDate: Date | null;
};
type Decision = { id: string; statement: string; rationale: string | null; owner: string | null; decidedAt: Date };
type Risk = { id: string; description: string; impact: string; mitigation: string | null; status: string };

const AI_STATES = ["open", "in_progress", "done", "cancelled"];
const RISK_STATES = ["open", "mitigated", "accepted", "closed"];

export function PendientesPanel({ processId, items }: { processId: string; items: ActionItem[] }) {
  return (
    <section className="card">
      <h2 className="section-title">Pendientes abiertos ({items.length})</h2>
      {items.length === 0 ? (
        <EmptyState title="Sin pendientes abiertos" />
      ) : (
        <ul className="mb-3 grid gap-2 text-sm">
          {items.map((a) => (
            <li key={a.id} className="rounded-lg border border-slate-200 p-2.5">
              <p className="text-slate-700">{a.description}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                {a.owner && <span>{a.owner}</span>}
                {a.dueDate && <span>· vence {fmtDate(a.dueDate)}</span>}
                <form action={updateActionItem} className="ml-auto flex items-center gap-1">
                  <input type="hidden" name="id" value={a.id} />
                  <input type="hidden" name="processId" value={processId} />
                  <select name="status" defaultValue={a.status} className="select w-auto px-2 py-1 text-xs">
                    {AI_STATES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  <button className="btn-ghost px-2 py-1 text-xs" type="submit">Guardar</button>
                </form>
                <form action={deleteActionItem}>
                  <input type="hidden" name="id" value={a.id} />
                  <input type="hidden" name="processId" value={processId} />
                  <button className="btn-danger px-2 py-1 text-xs" type="submit" title="Eliminar">✕</button>
                </form>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form action={addActionItem} className="grid gap-2 border-t border-slate-100 pt-3">
        <input type="hidden" name="processId" value={processId} />
        <input name="description" required className="input" placeholder="Nuevo pendiente…" />
        <div className="grid grid-cols-2 gap-2">
          <input name="owner" className="input" placeholder="Responsable" />
          <input type="date" name="dueDate" className="input" />
        </div>
        <button className="btn-ghost justify-center" type="submit">+ Añadir pendiente</button>
      </form>
    </section>
  );
}

export function RiesgosPanel({ processId, items }: { processId: string; items: Risk[] }) {
  return (
    <section className="card">
      <h2 className="section-title">Riesgos ({items.length})</h2>
      {items.length === 0 ? (
        <EmptyState title="Sin riesgos abiertos" />
      ) : (
        <ul className="mb-3 grid gap-2 text-sm">
          {items.map((r) => (
            <li key={r.id} className="rounded-lg border border-slate-200 p-2.5">
              <p className="text-slate-700">{r.description}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                <span className="text-slate-400">Impacto</span> <StatusBadge value={r.impact} />
                {r.mitigation && <span className="text-slate-500">· {r.mitigation}</span>}
                <form action={updateRisk} className="ml-auto flex items-center gap-1">
                  <input type="hidden" name="id" value={r.id} />
                  <input type="hidden" name="processId" value={processId} />
                  <select name="status" defaultValue={r.status} className="select w-auto px-2 py-1 text-xs">
                    {RISK_STATES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  <button className="btn-ghost px-2 py-1 text-xs" type="submit">Guardar</button>
                </form>
                <form action={deleteRisk}>
                  <input type="hidden" name="id" value={r.id} />
                  <input type="hidden" name="processId" value={processId} />
                  <button className="btn-danger px-2 py-1 text-xs" type="submit" title="Eliminar">✕</button>
                </form>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form action={addRisk} className="grid gap-2 border-t border-slate-100 pt-3">
        <input type="hidden" name="processId" value={processId} />
        <input name="description" required className="input" placeholder="Nuevo riesgo…" />
        <div className="grid grid-cols-2 gap-2">
          <select name="impact" defaultValue="medium" className="select">
            <option value="low">Impacto bajo</option>
            <option value="medium">Impacto medio</option>
            <option value="high">Impacto alto</option>
          </select>
          <input name="mitigation" className="input" placeholder="Mitigación" />
        </div>
        <button className="btn-ghost justify-center" type="submit">+ Añadir riesgo</button>
      </form>
    </section>
  );
}

export function DecisionesPanel({ processId, items }: { processId: string; items: Decision[] }) {
  return (
    <section className="card">
      <h2 className="section-title">Decisiones ({items.length})</h2>
      {items.length === 0 ? (
        <EmptyState title="Sin decisiones registradas" />
      ) : (
        <ul className="mb-3 grid gap-2 text-sm">
          {items.map((d) => (
            <li key={d.id} className="rounded-lg border border-slate-200 p-2.5">
              <div className="flex items-start gap-2">
                <p className="flex-1 text-slate-700">{d.statement}</p>
                <form action={deleteDecision}>
                  <input type="hidden" name="id" value={d.id} />
                  <input type="hidden" name="processId" value={processId} />
                  <button className="btn-danger px-2 py-1 text-xs" type="submit" title="Eliminar">✕</button>
                </form>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {d.owner ? `${d.owner} · ` : ""}{fmtDate(d.decidedAt)}{d.rationale ? ` · ${d.rationale}` : ""}
              </div>
            </li>
          ))}
        </ul>
      )}
      <form action={addDecision} className="grid gap-2 border-t border-slate-100 pt-3">
        <input type="hidden" name="processId" value={processId} />
        <input name="statement" required className="input" placeholder="Nueva decisión…" />
        <div className="grid grid-cols-2 gap-2">
          <input name="owner" className="input" placeholder="Responsable" />
          <input name="rationale" className="input" placeholder="Justificación" />
        </div>
        <button className="btn-ghost justify-center" type="submit">+ Añadir decisión</button>
      </form>
    </section>
  );
}
