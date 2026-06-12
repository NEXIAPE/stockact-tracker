import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { createProcess } from "@/app/actions";
import { Breadcrumbs, StatusBadge, EmptyState, fmtDate } from "@/components/ui";
import { StakeholdersPanel } from "@/components/StakeholdersPanel";

export const dynamic = "force-dynamic";

export default async function ProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    include: {
      stakeholders: { orderBy: [{ source: "asc" }, { name: "asc" }] },
      processes: {
        orderBy: { updatedAt: "desc" },
        include: { _count: { select: { meetings: true, actionItems: true, risks: true } } },
      },
    },
  });
  if (!project) notFound();

  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Proyectos" }, { label: project.name }]} />

      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
        <StatusBadge value={project.status} />
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <section>
          <h2 className="section-title">Procesos</h2>
          {project.processes.length === 0 ? (
            <EmptyState title="Este proyecto no tiene procesos" hint="Crea el primero con el formulario." />
          ) : (
            <ul className="grid gap-3">
              {project.processes.map((pr) => (
                <li key={pr.id}>
                  <Link href={`/processes/${pr.id}`} className="card flex items-center justify-between hover:border-brand-300">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{pr.name}</span>
                        <StatusBadge value={pr.status} />
                      </div>
                      <p className="mt-1 text-sm text-slate-500">
                        {pr._count.meetings} reunión(es) · {pr._count.actionItems} pendiente(s) · {pr._count.risks} riesgo(s)
                        {" · "}actualizado {fmtDate(pr.updatedAt)}
                      </p>
                    </div>
                    <span className="text-slate-300">→</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="grid gap-6">
          <div className="card">
            <h2 className="section-title">Nuevo proceso</h2>
            <form action={createProcess} className="grid gap-3">
              <input type="hidden" name="projectId" value={project.id} />
              <div>
                <label className="label">Nombre *</label>
                <input name="name" required className="input" placeholder="Ej. Aprobación de facturas" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label">Código</label>
                  <input name="code" className="input" placeholder="LOG-PD010" />
                </div>
                <div>
                  <label className="label">Área</label>
                  <input name="area" className="input" placeholder="Logística" />
                </div>
              </div>
              <div>
                <label className="label">Objetivo</label>
                <textarea name="objective" rows={2} className="textarea" placeholder="¿Qué busca lograr el proceso?" />
              </div>
              <div>
                <label className="label">Alcance</label>
                <textarea name="scope" rows={2} className="textarea" placeholder="Inicio y fin del proceso" />
              </div>
              <button className="btn justify-center" type="submit">Crear proceso</button>
            </form>
          </div>

          <StakeholdersPanel projectId={project.id} items={project.stakeholders} />
        </aside>
      </div>
    </div>
  );
}
