import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import {
  processMeetingAction,
  approveProposalAction,
  rejectProposalAction,
} from "@/app/actions";
import { Breadcrumbs, StatusBadge, EmptyState, fmtDate } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function MeetingPage({ params }: { params: Promise<{ meetingId: string }> }) {
  const { meetingId } = await params;
  const meeting = await prisma.meeting.findUnique({
    where: { id: meetingId },
    include: {
      process: { include: { project: true } },
      agreements: true,
      proposals: { orderBy: { createdAt: "asc" } },
    },
  });
  if (!meeting) notFound();

  const [actionItems, decisions, risks] = await Promise.all([
    prisma.actionItem.findMany({ where: { sourceMeetingId: meetingId } }),
    prisma.decision.findMany({ where: { sourceMeetingId: meetingId } }),
    prisma.risk.findMany({ where: { sourceMeetingId: meetingId } }),
  ]);

  const participants = (meeting.participants as string[]) ?? [];
  const isProcessed = meeting.processState === "processed";
  const pendingProposals = meeting.proposals.filter((p) => p.status === "pending");

  return (
    <div>
      <Breadcrumbs
        items={[
          { href: "/", label: "Proyectos" },
          { href: `/projects/${meeting.process.projectId}`, label: meeting.process.project.name },
          { href: `/processes/${meeting.processId}`, label: meeting.process.name },
          { label: meeting.title ?? "Reunión" },
        ]}
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{meeting.title ?? "Reunión"}</h1>
          <StatusBadge value={meeting.processState} />
          <span className="text-sm text-slate-500">{fmtDate(meeting.date)}</span>
        </div>
        <form action={processMeetingAction}>
          <input type="hidden" name="meetingId" value={meeting.id} />
          <button className="btn" type="submit">
            {isProcessed ? "↻ Reprocesar transcripción" : "▶ Procesar transcripción"}
          </button>
        </form>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Transcripción */}
        <section className="card">
          <h2 className="section-title">Transcripción</h2>
          {meeting.transcript ? (
            <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              {meeting.transcript}
            </pre>
          ) : (
            <EmptyState title="Sin transcripción" />
          )}
        </section>

        {/* Minuta (resumen + participantes) */}
        <section className="card">
          <h2 className="section-title">Minuta generada</h2>
          {meeting.summary ? (
            <>
              <p className="text-sm text-slate-700">{meeting.summary}</p>
              {participants.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {participants.map((p) => (
                    <span key={p} className="badge bg-brand-50 text-brand-700">{p}</span>
                  ))}
                </div>
              )}
              <p className="mt-3 text-xs text-slate-400">Procesado: {fmtDate(meeting.processedAt)}</p>
            </>
          ) : (
            <EmptyState title="Aún no procesada" hint="Pulsa «Procesar transcripción» para generar la minuta." />
          )}
        </section>
      </div>

      {/* Artefactos extraídos */}
      <div className="mt-6 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <ArtifactList title="Acuerdos" items={meeting.agreements.map((a) => a.text)} />
        <ArtifactList
          title="Pendientes"
          items={actionItems.map((a) => `${a.description}${a.owner ? ` — ${a.owner}` : ""}`)}
        />
        <ArtifactList
          title="Decisiones"
          items={decisions.map((d) => `${d.statement}${d.owner ? ` — ${d.owner}` : ""}`)}
        />
        <ArtifactList
          title="Riesgos"
          items={risks.map((r) => `${r.description} (${r.impact})`)}
        />
      </div>

      {/* Propuestas BPMN (human-in-the-loop) */}
      <section className="mt-8">
        <h2 className="section-title">
          Propuestas de cambio BPMN
          {pendingProposals.length > 0 && (
            <span className="ml-2 badge bg-amber-50 text-amber-700">{pendingProposals.length} pendiente(s)</span>
          )}
        </h2>
        {meeting.proposals.length === 0 ? (
          <EmptyState title="Sin propuestas de cambio" hint="El sistema propone cambios BPMN al procesar la transcripción." />
        ) : (
          <ul className="grid gap-3">
            {meeting.proposals.map((p) => (
              <li key={p.id} className="card">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="badge bg-slate-100 text-slate-600">{p.action}</span>
                      <span className="font-medium text-slate-800">{p.title}</span>
                      <StatusBadge value={p.status} />
                    </div>
                    {p.detail && <p className="mt-1 text-sm text-slate-500">{p.detail}</p>}
                  </div>
                  {p.status === "pending" && (
                    <div className="flex gap-2">
                      <form action={approveProposalAction}>
                        <input type="hidden" name="proposalId" value={p.id} />
                        <input type="hidden" name="meetingId" value={meeting.id} />
                        <button className="btn" type="submit">Aprobar</button>
                      </form>
                      <form action={rejectProposalAction}>
                        <input type="hidden" name="proposalId" value={p.id} />
                        <input type="hidden" name="meetingId" value={meeting.id} />
                        <button className="btn-danger" type="submit">Rechazar</button>
                      </form>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ArtifactList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="card">
      <h3 className="section-title">{title} <span className="text-slate-400">({items.length})</span></h3>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400">—</p>
      ) : (
        <ul className="grid gap-1.5 text-sm text-slate-700">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-brand-400">•</span>
              <span>{it}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
