import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700",
  on_hold: "bg-amber-50 text-amber-700",
  closed: "bg-slate-100 text-slate-600",
  discovery: "bg-sky-50 text-sky-700",
  design: "bg-indigo-50 text-indigo-700",
  validation: "bg-violet-50 text-violet-700",
  approved: "bg-emerald-50 text-emerald-700",
  deployed: "bg-teal-50 text-teal-700",
  open: "bg-amber-50 text-amber-700",
  in_progress: "bg-sky-50 text-sky-700",
  done: "bg-emerald-50 text-emerald-700",
  cancelled: "bg-slate-100 text-slate-500",
  high: "bg-rose-50 text-rose-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-emerald-50 text-emerald-700",
  pending: "bg-amber-50 text-amber-700",
  processed: "bg-emerald-50 text-emerald-700",
  processing: "bg-sky-50 text-sky-700",
  uploaded: "bg-slate-100 text-slate-600",
  error: "bg-rose-50 text-rose-700",
};

export function StatusBadge({ value }: { value: string }) {
  const cls = STATUS_COLORS[value] ?? "bg-slate-100 text-slate-600";
  return <span className={`badge ${cls}`}>{value.replace(/_/g, " ")}</span>;
}

export function Breadcrumbs({ items }: { items: { href?: string; label: string }[] }) {
  return (
    <nav className="mb-4 flex flex-wrap items-center gap-1.5 text-sm text-slate-500">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {it.href ? (
            <Link href={it.href} className="hover:text-brand-600">
              {it.label}
            </Link>
          ) : (
            <span className="font-medium text-slate-800">{it.label}</span>
          )}
          {i < items.length - 1 && <span className="text-slate-300">/</span>}
        </span>
      ))}
    </nav>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
      <p className="font-medium text-slate-600">{title}</p>
      {hint && <p className="mt-1">{hint}</p>}
    </div>
  );
}

export function fmtDate(d: Date | string | null | undefined): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("es", { year: "numeric", month: "short", day: "numeric" });
}
