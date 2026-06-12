import Link from "next/link";
import { prisma } from "@/lib/db";
import { createProject } from "./actions";
import { StatusBadge, EmptyState, fmtDate } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const projects = await prisma.project.findMany({
    orderBy: { updatedAt: "desc" },
    include: { _count: { select: { processes: true } } },
  });

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      <section>
        <h1 className="mb-1 text-2xl font-bold text-slate-900">Proyectos</h1>
        <p className="mb-6 text-sm text-slate-500">
          Cada proyecto agrupa uno o varios procesos. Selecciona uno para gestionar sus procesos y reuniones.
        </p>

        {projects.length === 0 ? (
          <EmptyState title="Aún no hay proyectos" hint="Crea tu primer proyecto con el formulario de la derecha." />
        ) : (
          <ul className="grid gap-3">
            {projects.map((p) => (
              <li key={p.id}>
                <Link href={`/projects/${p.id}`} className="card flex items-center justify-between hover:border-brand-300">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">{p.name}</span>
                      <StatusBadge value={p.status} />
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      {p.sponsor ? `Sponsor: ${p.sponsor} · ` : ""}
                      {p._count.processes} proceso(s) · inicio {fmtDate(p.startDate)}
                    </p>
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
          <h2 className="section-title">Nuevo proyecto</h2>
          <form action={createProject} className="grid gap-3">
            <div>
              <label className="label">Nombre *</label>
              <input name="name" required className="input" placeholder="Ej. Transformación Cuentas por Pagar" />
            </div>
            <div>
              <label className="label">Sponsor</label>
              <input name="sponsor" className="input" placeholder="Ej. Dirección Financiera" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Inicio</label>
                <input type="date" name="startDate" className="input" />
              </div>
              <div>
                <label className="label">Fin</label>
                <input type="date" name="endDate" className="input" />
              </div>
            </div>
            <button className="btn justify-center" type="submit">Crear proyecto</button>
          </form>
        </div>
      </aside>
    </div>
  );
}
