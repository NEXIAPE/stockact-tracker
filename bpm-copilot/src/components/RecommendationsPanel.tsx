import { analyzeProcessAction, acceptRecommendationAction, dismissRecommendationAction } from "@/app/actions";
import { CATEGORY_LABEL } from "@/core/domain/recommendation";
import { EmptyState } from "./ui";

type Rec = {
  id: string;
  category: string;
  severity: string;
  title: string;
  detail: string | null;
  suggestion: string | null;
  origin: string;
};

const SEV: Record<string, { dot: string; ring: string; label: string }> = {
  critical: { dot: "bg-rose-500", ring: "border-rose-200 bg-rose-50/40", label: "Crítico" },
  warning: { dot: "bg-amber-500", ring: "border-amber-200 bg-amber-50/40", label: "Atención" },
  info: { dot: "bg-sky-500", ring: "border-sky-200 bg-sky-50/40", label: "Info" },
};
const ORIGIN_LABEL: Record<string, string> = {
  linter: "auto",
  consultant_ai: "IA",
  meeting: "reunión",
};

export function RecommendationsPanel({ processId, items }: { processId: string; items: Rec[] }) {
  const order = { critical: 0, warning: 1, info: 2 } as Record<string, number>;
  const sorted = [...items].sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));

  return (
    <section className="card lg:col-span-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="section-title mb-0">
          🔎 Recomendaciones del consultor
          {items.length > 0 && <span className="ml-2 badge bg-brand-50 text-brand-700">{items.length}</span>}
        </h2>
        <form action={analyzeProcessAction}>
          <input type="hidden" name="processId" value={processId} />
          <button className="btn" type="submit">Auditar proceso</button>
        </form>
      </div>

      <p className="mb-3 text-xs text-slate-400">
        Propuestas proactivas: controles faltantes, actividades no mapeadas, owners sin definir y buenas prácticas BPMN.
        Pulsa «Auditar proceso» para regenerarlas sobre el BPMN consolidado.
      </p>

      {sorted.length === 0 ? (
        <EmptyState title="Sin recomendaciones abiertas" hint="Pulsa «Auditar proceso» o procesa una reunión." />
      ) : (
        <ul className="grid gap-2">
          {sorted.map((r) => {
            const sev = SEV[r.severity] ?? SEV.info;
            return (
              <li key={r.id} className={`rounded-lg border p-3 ${sev.ring}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${sev.dot}`} />
                      <span className="font-medium text-slate-800">{r.title}</span>
                      <span className="badge bg-slate-100 text-slate-500">{CATEGORY_LABEL[r.category] ?? r.category}</span>
                      <span className="badge bg-white text-slate-400 ring-1 ring-slate-200">{ORIGIN_LABEL[r.origin] ?? r.origin}</span>
                    </div>
                    {r.detail && <p className="mt-1 text-sm text-slate-600">{r.detail}</p>}
                    {r.suggestion && (
                      <p className="mt-1 text-sm text-slate-700">
                        <span className="font-medium text-brand-700">Propuesta:</span> {r.suggestion}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <form action={acceptRecommendationAction}>
                      <input type="hidden" name="id" value={r.id} />
                      <input type="hidden" name="processId" value={processId} />
                      <button className="btn px-3 py-1.5 text-xs" type="submit" title="Convierte en pendiente o riesgo">
                        Aceptar
                      </button>
                    </form>
                    <form action={dismissRecommendationAction}>
                      <input type="hidden" name="id" value={r.id} />
                      <input type="hidden" name="processId" value={processId} />
                      <button className="btn-ghost px-3 py-1.5 text-xs" type="submit">Descartar</button>
                    </form>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
