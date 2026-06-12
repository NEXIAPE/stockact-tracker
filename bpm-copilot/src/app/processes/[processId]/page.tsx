import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { createMeeting, updateProcessStatus } from "@/app/actions";
import { Breadcrumbs, StatusBadge, EmptyState, fmtDate } from "@/components/ui";
import { BpmnView } from "@/components/BpmnView";
import { BpmnModelSchema, emptyBpmnModel } from "@/core/domain/bpmn";

export const dynamic = "force-dynamic";

const PROCESS_STATES = ["discovery", "design", "validation", "approved", "deployed"];

export default async function ProcessPage({ params }: { params: Promise<{ processId: string }> }) {
  const { processId } = await params;
  const process = await prisma.process.findUnique({
    where: { id: processId },
    include: {
      project: true,
      currentVersion: true,
      meetings: { orderBy: { date: "desc" } },
      actionItems: { where: { status: { in: ["open", "in_progress"] } }, orderBy: { createdAt: "desc" } },
      risks: { where: { status: "open" }, orderBy: { createdAt: "desc" } },
      decisions: { orderBy: { decidedAt: "desc" }, take: 8 },
      changeLog: { orderBy: { createdAt: "desc" }, take: 8 },
      _count: { select: { proposals: true } },
    },
  });
  if (!process) notFound();

  const bpmn = process.currentVersion
    ? BpmnModelSchema.parse(process.currentVersion.bpmnModel)
    : emptyBpmnModel();
  const pendingProposals = await prisma.changeProposal.count({
    where: { processId, status: "pending" },
  });

  return (
    <div>
      <Breadcrumbs
        items={[
          { href: "/", label: "Proyectos" },
          { href: `/projects/${process.projectId}`, label: process.project.name },
          { label: process.name },
        ]}
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{process.name}</h1>
          <StatusBadge value={process.status} />
          {process.currentVersion && (
            <span className="badge bg-slate-100 text-slate-600">BPMN v{process.currentVersion.version}</span>
          )}
        </div>
        <form action={updateProcessStatus} className="flex items-center gap-2">
          <input type="hidden" name="processId" value={process.id} />
          <select name="status" defaultValue={process.status} className="select w-auto">
            {PROCESS_STATES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button className="btn-ghost" type="submit">Actualizar estado</button>
        </form>
      </div>

      {process.objective && <p className="mb-6 max-w-3xl text-sm text-slate-600">{process.objective}</p>}

      {pendingProposals > 0 && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Hay <strong>{pendingProposals}</strong> propuesta(s) de cambio pendiente(s) de revisión. Ábrelas desde la reunión correspondiente para aprobar o rechazar.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Columna principal: BPMN */}
        <section className="card lg:col-span-2">
          <h2 className="section-title">BPMN vigente</h2>
          <BpmnView model={bpmn} />
        </section>

        {/* Estado / contadores */}
        <section className="card">
          <h2 className="section-title">Estado del proceso</h2>
          <dl className="grid gap-2 text-sm">
            <Row k="Estado" v={<StatusBadge value={process.status} />} />
            <Row k="Versión BPMN" v={process.currentVersion ? `v${process.currentVersion.version}` : "—"} />
            <Row k="Reuniones" v={String(process.meetings.length)} />
            <Row k="Pendientes abiertos" v={String(process.actionItems.length)} />
            <Row k="Riesgos abiertos" v={String(process.risks.length)} />
            <Row k="Alcance" v={process.scope ?? "—"} />
          </dl>
        </section>

        {/* Pendientes */}
        <section className="card">
          <h2 className="section-title">Pendientes abiertos</h2>
          {process.actionItems.length === 0 ? (
            <EmptyState title="Sin pendientes abiertos" />
          ) : (
            <ul className="grid gap-2 text-sm">
              {process.actionItems.map((a) => (
                <li key={a.id} className="rounded-lg border border-slate-200 p-2.5">
                  <p className="text-slate-700">{a.description}</p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    <StatusBadge value={a.status} />
                    {a.owner && <span>· {a.owner}</span>}
                    {a.dueDate && <span>· vence {fmtDate(a.dueDate)}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Riesgos */}
        <section className="card">
          <h2 className="section-title">Riesgos</h2>
          {process.risks.length === 0 ? (
            <EmptyState title="Sin riesgos abiertos" />
          ) : (
            <ul className="grid gap-2 text-sm">
              {process.risks.map((r) => (
                <li key={r.id} className="rounded-lg border border-slate-200 p-2.5">
                  <p className="text-slate-700">{r.description}</p>
                  <div className="mt-1 flex items-center gap-2 text-xs">
                    <span className="text-slate-400">Impacto</span> <StatusBadge value={r.impact} />
                    {r.mitigation && <span className="text-slate-500">· {r.mitigation}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Decisiones */}
        <section className="card">
          <h2 className="section-title">Decisiones</h2>
          {process.decisions.length === 0 ? (
            <EmptyState title="Sin decisiones registradas" />
          ) : (
            <ul className="grid gap-2 text-sm">
              {process.decisions.map((d) => (
                <li key={d.id} className="rounded-lg border border-slate-200 p-2.5">
                  <p className="text-slate-700">{d.statement}</p>
                  <div className="mt-1 text-xs text-slate-500">
                    {d.owner ? `${d.owner} · ` : ""}{fmtDate(d.decidedAt)}
                    {d.rationale ? ` · ${d.rationale}` : ""}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Últimos cambios */}
        <section className="card lg:col-span-3">
          <h2 className="section-title">Últimos cambios</h2>
          {process.changeLog.length === 0 ? (
            <EmptyState title="Sin actividad registrada" />
          ) : (
            <ul className="grid gap-1.5 text-sm">
              {process.changeLog.map((c) => (
                <li key={c.id} className="flex items-center gap-3 border-b border-slate-100 py-1.5 last:border-0">
                  <StatusBadge value={c.action} />
                  <span className="text-slate-700">{c.summary}</span>
                  <span className="ml-auto text-xs text-slate-400">{fmtDate(c.createdAt)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Reuniones */}
      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_360px]">
        <section>
          <h2 className="section-title">Reuniones</h2>
          {process.meetings.length === 0 ? (
            <EmptyState title="Sin reuniones" hint="Sube tu primera transcripción con el formulario." />
          ) : (
            <ul className="grid gap-3">
              {process.meetings.map((m) => (
                <li key={m.id}>
                  <Link href={`/meetings/${m.id}`} className="card flex items-center justify-between hover:border-brand-300">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{m.title ?? "Reunión"}</span>
                        <StatusBadge value={m.processState} />
                      </div>
                      <p className="mt-1 text-sm text-slate-500">{fmtDate(m.date)}</p>
                    </div>
                    <span className="text-slate-300">→</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside>
          <div className="card sticky top-6">
            <h2 className="section-title">Nueva reunión</h2>
            <form action={createMeeting} className="grid gap-3">
              <input type="hidden" name="processId" value={process.id} />
              <div>
                <label className="label">Título</label>
                <input name="title" className="input" placeholder="Ej. Validación con Tesorería" />
              </div>
              <div>
                <label className="label">Fecha</label>
                <input type="date" name="date" className="input" />
              </div>
              <div>
                <label className="label">Transcripción</label>
                <textarea name="transcript" rows={6} className="textarea" placeholder="Pega aquí la transcripción de Teams…" />
              </div>
              <button className="btn justify-center" type="submit">Crear y abrir</button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-slate-100 py-1.5 last:border-0">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  );
}
