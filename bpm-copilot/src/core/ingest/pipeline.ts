/**
 * Pipeline de ingesta de una reunión.
 *
 * Orquesta: transcripción -> LLM -> persistencia de minuta + artefactos
 * consolidados + PROPUESTAS de cambio BPMN (human-in-the-loop) + historial.
 *
 * Idempotente: reprocesar una reunión limpia sus artefactos previos (por
 * sourceMeetingId) antes de re-insertar, evitando duplicados.
 */
import { createHash } from "node:crypto";
import { prisma } from "@/lib/db";
import { getLlm } from "@/core/ai/factory";
import { BpmnModelSchema, emptyBpmnModel, type BpmnModel } from "@/core/domain/bpmn";

export async function processMeeting(meetingId: string): Promise<void> {
  const meeting = await prisma.meeting.findUniqueOrThrow({
    where: { id: meetingId },
    include: { process: true },
  });

  if (!meeting.transcript || meeting.transcript.trim().length === 0) {
    throw new Error("La reunión no tiene transcripción.");
  }

  await prisma.meeting.update({
    where: { id: meetingId },
    data: { processState: "processing" },
  });

  try {
    // --- Contexto del Proceso Vivo ---
    const currentVersion = meeting.process.currentVersionId
      ? await prisma.processVersion.findUnique({ where: { id: meeting.process.currentVersionId } })
      : null;
    const currentBpmn: BpmnModel = currentVersion
      ? BpmnModelSchema.parse(currentVersion.bpmnModel)
      : emptyBpmnModel();

    const priorMeetings = await prisma.meeting.findMany({
      where: { processId: meeting.processId, processState: "processed", id: { not: meetingId } },
      orderBy: { date: "asc" },
      select: { summary: true },
    });
    const priorSummaries = priorMeetings.map((m) => m.summary).filter((s): s is string => !!s);

    // --- Extracción IA (adaptador agnóstico) ---
    const llm = getLlm();
    const extraction = await llm.extractFromTranscript(meeting.transcript, {
      processName: meeting.process.name,
      processObjective: meeting.process.objective,
      currentBpmn,
      priorSummaries,
    });

    const hash = createHash("sha256").update(meeting.transcript).digest("hex");

    // --- Limpieza idempotente de artefactos previos de ESTA reunión ---
    await prisma.$transaction([
      prisma.agreement.deleteMany({ where: { meetingId } }),
      prisma.actionItem.deleteMany({ where: { sourceMeetingId: meetingId } }),
      prisma.decision.deleteMany({ where: { sourceMeetingId: meetingId } }),
      prisma.risk.deleteMany({ where: { sourceMeetingId: meetingId } }),
      prisma.changeProposal.deleteMany({ where: { meetingId, status: "pending" } }),
    ]);

    // --- Persistencia de minuta + artefactos ---
    await prisma.meeting.update({
      where: { id: meetingId },
      data: {
        summary: extraction.summary,
        participants: extraction.participants,
        transcriptHash: hash,
        processState: "processed",
        processedAt: new Date(),
        rawExtraction: extraction as object,
        agreements: { create: extraction.agreements.map((a) => ({ text: a.text })) },
      },
    });

    const pid = meeting.processId;

    // --- Stakeholders: consolidación a nivel de PROYECTO (enriquecer, no pisar) ---
    const projectId = meeting.process.projectId;
    for (const s of extraction.stakeholders) {
      const name = s.name.trim();
      if (!name) continue;
      const existing = await prisma.stakeholder.findUnique({
        where: { projectId_name: { projectId, name } },
      });
      if (!existing) {
        await prisma.stakeholder.create({
          data: { projectId, name, role: s.role ?? null, area: s.area ?? null, source: "meeting" },
        });
      } else {
        // Solo completa campos vacíos; nunca sobrescribe datos ya validados.
        const data: { role?: string; area?: string } = {};
        if (!existing.role && s.role) data.role = s.role;
        if (!existing.area && s.area) data.area = s.area;
        if (Object.keys(data).length) {
          await prisma.stakeholder.update({ where: { id: existing.id }, data });
        }
      }
    }

    if (extraction.actionItems.length) {
      await prisma.actionItem.createMany({
        data: extraction.actionItems.map((a) => ({
          processId: pid,
          sourceMeetingId: meetingId,
          description: a.description,
          owner: a.owner ?? null,
          dueDate: a.dueDate ? new Date(a.dueDate) : null,
        })),
      });
    }
    if (extraction.decisions.length) {
      await prisma.decision.createMany({
        data: extraction.decisions.map((d) => ({
          processId: pid,
          sourceMeetingId: meetingId,
          statement: d.statement,
          rationale: d.rationale ?? null,
          owner: d.owner ?? null,
        })),
      });
    }
    if (extraction.risks.length) {
      await prisma.risk.createMany({
        data: extraction.risks.map((r) => ({
          processId: pid,
          sourceMeetingId: meetingId,
          description: r.description,
          impact: r.impact,
          likelihood: r.likelihood,
          mitigation: r.mitigation ?? null,
        })),
      });
    }

    // --- Cambios BPMN como PROPUESTAS pendientes (human-in-the-loop) ---
    if (extraction.bpmnChanges.length) {
      await prisma.changeProposal.createMany({
        data: extraction.bpmnChanges.map((c) => ({
          processId: pid,
          meetingId,
          target: "bpmn",
          action: c.action,
          title: c.title,
          detail: c.detail ?? null,
          payload: c.fragment as object,
          status: "pending",
        })),
      });
    }

    // --- Historial ---
    await prisma.changeLogEntry.create({
      data: {
        processId: pid,
        sourceMeetingId: meetingId,
        entity: "process",
        action: "updated",
        summary:
          `Reunión procesada: ${extraction.agreements.length} acuerdos, ` +
          `${extraction.decisions.length} decisiones, ${extraction.actionItems.length} pendientes, ` +
          `${extraction.risks.length} riesgos, ${extraction.bpmnChanges.length} propuestas BPMN.`,
      },
    });
  } catch (err) {
    await prisma.meeting.update({
      where: { id: meetingId },
      data: { processState: "error" },
    });
    throw err;
  }
}
