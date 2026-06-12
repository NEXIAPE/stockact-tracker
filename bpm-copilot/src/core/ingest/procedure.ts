/** Genera y persiste un Procedimiento desde el proceso consolidado. */
import { prisma } from "@/lib/db";
import { BpmnModelSchema, emptyBpmnModel } from "@/core/domain/bpmn";
import { buildProcedure } from "@/core/domain/procedure";

export async function generateProcedure(processId: string): Promise<string> {
  const process = await prisma.process.findUniqueOrThrow({
    where: { id: processId },
    include: { currentVersion: true },
  });
  const [decisions, risks, stakeholders, last] = await Promise.all([
    prisma.decision.findMany({ where: { processId }, orderBy: { decidedAt: "asc" } }),
    prisma.risk.findMany({ where: { processId, status: { not: "closed" } } }),
    prisma.stakeholder.findMany({ where: { projectId: process.projectId }, orderBy: { name: "asc" } }),
    prisma.procedure.findFirst({ where: { processId }, orderBy: { version: "desc" } }),
  ]);

  const bpmn = process.currentVersion
    ? BpmnModelSchema.parse(process.currentVersion.bpmnModel)
    : emptyBpmnModel();

  const sections = buildProcedure({
    processName: process.name,
    code: process.code,
    area: process.area,
    version: (last?.version ?? 0) + 1,
    objective: process.objective,
    scope: process.scope,
    bpmn,
    stakeholders: stakeholders.map((s) => ({ name: s.name, role: s.role, area: s.area })),
    decisions: decisions.map((d) => ({ statement: d.statement, rationale: d.rationale, owner: d.owner })),
    risks: risks.map((r) => ({ description: r.description, impact: r.impact, mitigation: r.mitigation })),
  });
  const proc = await prisma.procedure.create({
    data: { processId, version: (last?.version ?? 0) + 1, sections: sections as object },
  });

  await prisma.changeLogEntry.create({
    data: {
      processId,
      entity: "procedure",
      action: "created",
      summary: `Procedimiento v${proc.version} generado desde el proceso consolidado.`,
    },
  });

  return proc.id;
}
