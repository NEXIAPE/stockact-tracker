/**
 * Auditoría del proceso (consultor). Combina:
 *  - Linter determinista (siempre, coste cero).
 *  - Auditoría por IA (si el proveedor la implementa; mock devuelve []).
 * Persiste recomendaciones nuevas sin reintroducir las ya descartadas/aceptadas.
 */
import { prisma } from "@/lib/db";
import { getLlm } from "@/core/ai/factory";
import { BpmnModelSchema, emptyBpmnModel } from "@/core/domain/bpmn";
import { lintProcess } from "@/core/domain/linter";
import type { RecommendationDraft } from "@/core/domain/recommendation";

const OWNER_CARGO = /\b(gerent|jefe|jefa|coordinador|director|owner|due[ñn]o)/i;

export async function analyzeProcess(processId: string): Promise<number> {
  const process = await prisma.process.findUniqueOrThrow({
    where: { id: processId },
    include: { currentVersion: true },
  });
  const [decisions, risks, stakeholders] = await Promise.all([
    prisma.decision.findMany({ where: { processId } }),
    prisma.risk.findMany({ where: { processId, status: { not: "closed" } } }),
    prisma.stakeholder.findMany({ where: { projectId: process.projectId } }),
  ]);

  const bpmn = process.currentVersion
    ? BpmnModelSchema.parse(process.currentVersion.bpmnModel)
    : emptyBpmnModel();

  // 1) Linter determinista
  const linterRecs = lintProcess(bpmn, {
    kind: process.kind,
    riskCount: risks.length,
    hasPolicies: decisions.length > 0,
    hasOwnerStakeholder: stakeholders.some((s) => OWNER_CARGO.test(s.role ?? "")),
  });

  // 2) Auditoría por IA (best-effort; no rompe si falla o no aplica)
  let aiRecs: RecommendationDraft[] = [];
  try {
    aiRecs = await getLlm().auditProcess({
      processName: process.name,
      processObjective: process.objective,
      processKind: process.kind,
      currentBpmn: bpmn,
      decisions: decisions.map((d) => d.statement),
      risks: risks.map((r) => r.description),
    });
  } catch (err) {
    console.warn("[analyze] auditoría IA falló, se usa solo el linter:", err);
  }

  // Limpia recomendaciones abiertas auto-generadas previas (no toca aceptadas/descartadas).
  await prisma.recommendation.deleteMany({
    where: { processId, origin: { in: ["linter", "consultant_ai"] }, status: "open" },
  });

  // Evita reintroducir títulos ya aceptados/descartados por el usuario.
  const resolved = await prisma.recommendation.findMany({
    where: { processId, status: { in: ["accepted", "dismissed"] } },
    select: { title: true },
  });
  const skip = new Set(resolved.map((r) => r.title.toLowerCase()));

  const toCreate = [
    ...linterRecs.map((r) => ({ ...r, origin: "linter" })),
    ...aiRecs.map((r) => ({ ...r, origin: "consultant_ai" })),
  ].filter((r) => !skip.has(r.title.toLowerCase()));

  // Dedup por título dentro del mismo lote.
  const seen = new Set<string>();
  let created = 0;
  for (const r of toCreate) {
    const key = r.title.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    await prisma.recommendation.create({
      data: {
        processId,
        category: r.category,
        severity: r.severity,
        title: r.title,
        detail: r.detail ?? null,
        suggestion: r.suggestion ?? null,
        status: "open",
        origin: r.origin,
      },
    });
    created++;
  }

  await prisma.changeLogEntry.create({
    data: {
      processId,
      entity: "process",
      action: "updated",
      summary: `Auditoría del consultor: ${created} recomendación(es) (${linterRecs.length} linter, ${aiRecs.length} IA).`,
    },
  });

  return created;
}
