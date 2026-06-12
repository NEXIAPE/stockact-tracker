import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { generateProcedureAction } from "@/app/actions";
import { Breadcrumbs, EmptyState, fmtDate } from "@/components/ui";
import MermaidDiagram from "@/components/MermaidDiagram";
import { procedureToMarkdown, type ProcedureSection } from "@/core/domain/procedure";

export const dynamic = "force-dynamic";

/** Render mínimo de Markdown (negritas, cursivas, listas, código). */
function renderInline(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/_(.+?)_/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, '<code class="rounded bg-slate-100 px-1 text-xs">$1</code>');
}

function SectionBody({ section }: { section: ProcedureSection }) {
  // Anexo BPMN: extrae y renderiza el diagrama Mermaid visualmente.
  const mermaid = section.body.match(/```mermaid\n([\s\S]*?)\n```/);
  if (mermaid) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-3">
        <MermaidDiagram chart={mermaid[1]} />
      </div>
    );
  }
  const lines = section.body.split("\n");
  return (
    <div className="space-y-1 text-sm text-slate-700">
      {lines.map((ln, i) =>
        ln.trim().startsWith("- ") ? (
          <p key={i} className="flex gap-2 pl-1">
            <span className="text-brand-400">•</span>
            <span dangerouslySetInnerHTML={{ __html: renderInline(ln.replace(/^- /, "")) }} />
          </p>
        ) : (
          <p key={i} dangerouslySetInnerHTML={{ __html: renderInline(ln) }} />
        )
      )}
    </div>
  );
}

export default async function ProcedurePage({ params }: { params: Promise<{ processId: string }> }) {
  const { processId } = await params;
  const process = await prisma.process.findUnique({
    where: { id: processId },
    include: { project: true },
  });
  if (!process) notFound();

  const procedure = await prisma.procedure.findFirst({
    where: { processId },
    orderBy: { version: "desc" },
  });
  const sections = (procedure?.sections as unknown as ProcedureSection[]) ?? [];
  const markdown = procedure ? procedureToMarkdown(process.name, sections) : "";

  return (
    <div>
      <Breadcrumbs
        items={[
          { href: "/", label: "Proyectos" },
          { href: `/projects/${process.projectId}`, label: process.project.name },
          { href: `/processes/${processId}`, label: process.name },
          { label: "Procedimiento" },
        ]}
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">Procedimiento</h1>
          {procedure && <span className="badge bg-slate-100 text-slate-600">v{procedure.version}</span>}
          {procedure && <span className="text-sm text-slate-500">generado {fmtDate(procedure.createdAt)}</span>}
        </div>
        <form action={generateProcedureAction}>
          <input type="hidden" name="processId" value={processId} />
          <button className="btn" type="submit">{procedure ? "↻ Regenerar" : "▶ Generar procedimiento"}</button>
        </form>
      </div>

      {!procedure ? (
        <EmptyState
          title="Aún no se ha generado el procedimiento"
          hint="Se construye automáticamente desde el proceso consolidado (BPMN, decisiones, riesgos). Pulsa «Generar»."
        />
      ) : (
        <>
          <div className="grid gap-5">
            {sections.map((s) => (
              <section key={s.key} className="card">
                <h2 className="mb-2 text-base font-semibold text-slate-900">{s.title}</h2>
                <SectionBody section={s} />
              </section>
            ))}
          </div>

          <details className="mt-6 card">
            <summary className="cursor-pointer section-title">Exportar a Markdown</summary>
            <textarea readOnly rows={16} className="textarea mt-3 font-mono text-xs" value={markdown} />
          </details>
        </>
      )}

      <div className="mt-6">
        <Link href={`/processes/${processId}`} className="btn-ghost">← Volver al proceso</Link>
      </div>
    </div>
  );
}
