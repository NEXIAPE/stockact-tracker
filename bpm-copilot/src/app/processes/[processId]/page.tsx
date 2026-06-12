import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { createMeeting, updateProcessStatus, updateProcessMeta } from "@/app/actions";
import { Breadcrumbs, StatusBadge, EmptyState, fmtDate } from "@/components/ui";
import { BpmnView } from "@/components/BpmnView";
import { PendientesPanel, RiesgosPanel, DecisionesPanel } from "@/components/ArtifactPanels";
import { RecommendationsPanel } from "@/components/RecommendationsPanel";
import { BpmnModelSchema, emptyBpmnModel } from "@/core/domain/bpmn";

export const dynamic = "force-dynamic";

const PROCESS_STATES = ["discovery", "design", "validation", "approved", "deployed"];
const KIND_LABEL: Record<string, string> = {
  new: "Proceso nuevo",
  improvement: "Mejora de existente",
  owner_definition: "Definición de owner",
  normative: "Normativo / cumplimiento",
};

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
      recommendations: { where: { status: "open" }, orderBy: { createdAt: "desc" } },
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
          {process.code && <span className="badge bg-brand-50 text-brand-700">{process.code}</span>}
          <h1 className="text-2xl font-bold text-slate-900">{process.name}</h1>
          <StatusBadge value={process.status} />
          <span className="badge bg-violet-50 text-violet-700">{KIND_LABEL[process.kind] ?? process.kind}</span>
          {process.area && <span className="badge bg-slate-100 text-slate-600">{process.area}</span>}
          {process.currentVersion && (
            <span className="badge bg-slate-100 text-slate-600">BPMN v{process.currentVersion.version}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/processes/${process.id}/procedure`} className="btn-ghost">📄 Procedimiento</Link>
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
          <form action={updateProcessMeta} className="mt-3 grid gap-2 border-t border-slate-100 pt-3">
            <input type="hidden" name="processId" value={process.id} />
            <label className="label">Código y área (cabecera del procedimiento)</label>
            <div className="grid grid-cols-2 gap-2">
              <input name="code" defaultValue={process.code ?? ""} className="input" placeholder="LOG-PD010" />
              <input name="area" defaultValue={process.area ?? ""} className="input" placeholder="Logística" />
            </div>
            <button type="submit" className="btn-ghost justify-center">Guardar código/área</button>
          </form>
        </section>

        {/* Pendientes / Riesgos / Decisiones (editables) */}
        <PendientesPanel processId={process.id} items={process.actionItems} />
        <RiesgosPanel processId={process.id} items={process.risks} />
        <DecisionesPanel processId={process.id} items={process.decisions} />

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

        {/* Recomendaciones del consultor (propone proactivamente) */}
        <RecommendationsPanel processId={process.id} items={process.recommendations} />
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
              <div>
                <label className="label">…o importar archivo (.txt / .vtt / .srt)</label>
                <input type="file" name="file" accept=".txt,.vtt,.srt,text/plain" className="input file:mr-3 file:rounded file:border-0 file:bg-brand-50 file:px-3 file:py-1 file:text-brand-700" />
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
