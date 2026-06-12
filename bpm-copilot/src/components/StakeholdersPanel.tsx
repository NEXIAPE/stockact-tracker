import { addStakeholder, updateStakeholder, deleteStakeholder } from "@/app/actions";
import { EmptyState } from "./ui";

type Stakeholder = {
  id: string;
  name: string;
  role: string | null;
  area: string | null;
  source: string;
};

/**
 * Stakeholders del proyecto. Se identifican automáticamente desde las
 * transcripciones (source=meeting) y pueden editarse/añadirse a mano.
 */
export function StakeholdersPanel({ projectId, items }: { projectId: string; items: Stakeholder[] }) {
  return (
    <div className="card">
      <h2 className="section-title">Stakeholders ({items.length})</h2>
      <p className="mb-3 text-xs text-slate-400">
        Detectados desde transcripciones y editables. Alimentan los roles del procedimiento.
      </p>

      {items.length === 0 ? (
        <EmptyState title="Aún no hay stakeholders" hint="Procesa una reunión o añádelos manualmente." />
      ) : (
        <div className="mb-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="py-1 pr-2">Nombre</th>
                <th className="py-1 pr-2">Cargo / Área (editable)</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className="border-t border-slate-100 align-middle">
                  <td className="py-1.5 pr-2 font-medium text-slate-700">
                    {s.name}
                    {s.source === "meeting" && (
                      <span className="ml-1 badge bg-sky-50 text-sky-600" title="Detectado en reunión">auto</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2">
                    <form action={updateStakeholder} className="flex items-center gap-1">
                      <input type="hidden" name="id" value={s.id} />
                      <input type="hidden" name="projectId" value={projectId} />
                      <input name="role" defaultValue={s.role ?? ""} placeholder="cargo" className="input px-2 py-1 text-xs" />
                      <input name="area" defaultValue={s.area ?? ""} placeholder="área" className="input px-2 py-1 text-xs" />
                      <button type="submit" className="btn-ghost px-2 py-1 text-xs">✓</button>
                    </form>
                  </td>
                  <td className="py-1.5">
                    <form action={deleteStakeholder}>
                      <input type="hidden" name="id" value={s.id} />
                      <input type="hidden" name="projectId" value={projectId} />
                      <button type="submit" className="btn-danger px-2 py-1 text-xs" title="Eliminar">✕</button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form action={addStakeholder} className="grid gap-2 border-t border-slate-100 pt-3">
        <input type="hidden" name="projectId" value={projectId} />
        <input name="name" required className="input" placeholder="Nombre del stakeholder" />
        <div className="grid grid-cols-2 gap-2">
          <input name="role" className="input" placeholder="Cargo" />
          <input name="area" className="input" placeholder="Área" />
        </div>
        <button type="submit" className="btn-ghost justify-center">+ Añadir stakeholder</button>
      </form>
    </div>
  );
}
