/**
 * Aprobación / rechazo de propuestas de cambio (human-in-the-loop).
 * Aprobar una propuesta BPMN crea una NUEVA ProcessVersion (versionado).
 */
import { prisma } from "@/lib/db";
import { BpmnModelSchema, emptyBpmnModel, type BpmnModel } from "@/core/domain/bpmn";
import { applyFragment } from "@/core/domain/bpmn-merge";

export async function approveProposal(proposalId: string, reviewer: string): Promise<void> {
  const proposal = await prisma.changeProposal.findUniqueOrThrow({
    where: { id: proposalId },
    include: { process: true },
  });
  if (proposal.status !== "pending") return;

  if (proposal.target === "bpmn") {
    const current = proposal.process.currentVersionId
      ? await prisma.processVersion.findUnique({ where: { id: proposal.process.currentVersionId } })
      : null;
    const currentBpmn: BpmnModel = current
      ? BpmnModelSchema.parse(current.bpmnModel)
      : emptyBpmnModel();

    const nextModel = applyFragment(
      currentBpmn,
      proposal.action as "add" | "update" | "remove",
      proposal.payload as Partial<BpmnModel>
    );

    const lastVersion = await prisma.processVersion.findFirst({
      where: { processId: proposal.processId },
      orderBy: { version: "desc" },
    });
    const nextNumber = (lastVersion?.version ?? 0) + 1;

    const newVersion = await prisma.processVersion.create({
      data: {
        processId: proposal.processId,
        version: nextNumber,
        label: proposal.title,
        bpmnModel: nextModel as object,
        sourceMeetingId: proposal.meetingId,
        createdById: reviewer,
      },
    });

    await prisma.process.update({
      where: { id: proposal.processId },
      data: { currentVersionId: newVersion.id },
    });

    await prisma.changeLogEntry.create({
      data: {
        processId: proposal.processId,
        sourceMeetingId: proposal.meetingId,
        entity: "bpmn",
        action: "approved",
        summary: `BPMN v${nextNumber}: ${proposal.title}`,
        requestedBy: reviewer,
        diff: proposal.payload as object,
      },
    });
  }

  await prisma.changeProposal.update({
    where: { id: proposalId },
    data: { status: "approved", reviewedBy: reviewer, reviewedAt: new Date() },
  });
}

export async function rejectProposal(proposalId: string, reviewer: string): Promise<void> {
  const proposal = await prisma.changeProposal.findUniqueOrThrow({ where: { id: proposalId } });
  if (proposal.status !== "pending") return;

  await prisma.changeProposal.update({
    where: { id: proposalId },
    data: { status: "rejected", reviewedBy: reviewer, reviewedAt: new Date() },
  });
  await prisma.changeLogEntry.create({
    data: {
      processId: proposal.processId,
      sourceMeetingId: proposal.meetingId,
      entity: "bpmn",
      action: "rejected",
      summary: `Propuesta rechazada: ${proposal.title}`,
      requestedBy: reviewer,
    },
  });
}
