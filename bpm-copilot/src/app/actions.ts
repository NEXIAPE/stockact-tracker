"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { processMeeting } from "@/core/ingest/pipeline";
import { approveProposal, rejectProposal } from "@/core/ingest/proposals";
import { generateProcedure } from "@/core/ingest/procedure";
import { analyzeProcess } from "@/core/ingest/analyze";
import { normalizeTranscript } from "@/core/ingest/transcript";

const REVIEWER = "admin@nexia.fit"; // MVP local-first: usuario único. Multiusuario en fase SaaS.

// -------------------- Proyectos --------------------
export async function createProject(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return;
  const project = await prisma.project.create({
    data: {
      name,
      sponsor: str(formData.get("sponsor")),
      startDate: date(formData.get("startDate")),
      endDate: date(formData.get("endDate")),
    },
  });
  revalidatePath("/");
  redirect(`/projects/${project.id}`);
}

// -------------------- Procesos --------------------
export async function createProcess(formData: FormData) {
  const projectId = String(formData.get("projectId") ?? "");
  const name = String(formData.get("name") ?? "").trim();
  if (!projectId || !name) return;
  const process = await prisma.process.create({
    data: {
      projectId,
      name,
      code: str(formData.get("code")),
      area: str(formData.get("area")),
      kind: String(formData.get("kind") ?? "new"),
      objective: str(formData.get("objective")),
      scope: str(formData.get("scope")),
    },
  });
  revalidatePath(`/projects/${projectId}`);
  redirect(`/processes/${process.id}`);
}

export async function updateProcessStatus(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  const status = String(formData.get("status") ?? "");
  await prisma.process.update({ where: { id: processId }, data: { status } });
  revalidatePath(`/processes/${processId}`);
}

export async function updateProcessMeta(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  await prisma.process.update({
    where: { id: processId },
    data: { code: str(formData.get("code")), area: str(formData.get("area")) },
  });
  revalidatePath(`/processes/${processId}`);
}

// -------------------- Consultor / Recomendaciones --------------------
export async function analyzeProcessAction(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  if (!processId) return;
  await analyzeProcess(processId);
  revalidatePath(`/processes/${processId}`);
}

export async function acceptRecommendationAction(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  const rec = await prisma.recommendation.findUniqueOrThrow({ where: { id } });
  if (rec.status !== "open") return;

  const text = rec.suggestion ? `${rec.title} — ${rec.suggestion}` : rec.title;
  if (rec.category === "risk") {
    await prisma.risk.create({
      data: { processId, description: text, impact: rec.severity === "critical" ? "high" : "medium", sourceMeetingId: rec.sourceMeetingId },
    });
  } else {
    await prisma.actionItem.create({
      data: { processId, description: text, sourceMeetingId: rec.sourceMeetingId },
    });
  }
  await prisma.recommendation.update({ where: { id }, data: { status: "accepted" } });
  await prisma.changeLogEntry.create({
    data: { processId, entity: "process", action: "approved", summary: `Recomendación aceptada: ${rec.title}`, requestedBy: REVIEWER },
  });
  revalidatePath(`/processes/${processId}`);
}

export async function dismissRecommendationAction(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  await prisma.recommendation.update({ where: { id }, data: { status: "dismissed" } });
  revalidatePath(`/processes/${processId}`);
}

// -------------------- Stakeholders --------------------
export async function addStakeholder(formData: FormData) {
  const projectId = String(formData.get("projectId") ?? "");
  const name = String(formData.get("name") ?? "").trim();
  if (!projectId || !name) return;
  await prisma.stakeholder.upsert({
    where: { projectId_name: { projectId, name } },
    create: { projectId, name, role: str(formData.get("role")), area: str(formData.get("area")), source: "manual" },
    update: { role: str(formData.get("role")), area: str(formData.get("area")) },
  });
  revalidatePath(`/projects/${projectId}`);
}
export async function updateStakeholder(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const projectId = String(formData.get("projectId") ?? "");
  await prisma.stakeholder.update({
    where: { id },
    data: { role: str(formData.get("role")), area: str(formData.get("area")) },
  });
  revalidatePath(`/projects/${projectId}`);
}
export async function deleteStakeholder(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const projectId = String(formData.get("projectId") ?? "");
  await prisma.stakeholder.delete({ where: { id } });
  revalidatePath(`/projects/${projectId}`);
}

// -------------------- Reuniones --------------------
export async function createMeeting(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  const title = str(formData.get("title"));
  let transcript = str(formData.get("transcript"));

  // Importación desde archivo (.txt / .vtt / .srt) — prevalece si se adjunta.
  const file = formData.get("file");
  if (file instanceof File && file.size > 0) {
    transcript = normalizeTranscript(await file.text());
  }

  if (!processId) return;
  const meeting = await prisma.meeting.create({
    data: { processId, title, transcript, date: date(formData.get("date")) ?? new Date() },
  });
  revalidatePath(`/processes/${processId}`);
  redirect(`/meetings/${meeting.id}`);
}

export async function updateMeeting(formData: FormData) {
  const meetingId = String(formData.get("meetingId") ?? "");
  await prisma.meeting.update({
    where: { id: meetingId },
    data: { title: str(formData.get("title")), transcript: str(formData.get("transcript")) },
  });
  revalidatePath(`/meetings/${meetingId}`);
}

export async function processMeetingAction(formData: FormData) {
  const meetingId = String(formData.get("meetingId") ?? "");
  if (!meetingId) return;
  await processMeeting(meetingId);
  revalidatePath(`/meetings/${meetingId}`);
}

// -------------------- Propuestas (human-in-the-loop) --------------------
export async function approveProposalAction(formData: FormData) {
  await approveProposal(String(formData.get("proposalId") ?? ""), REVIEWER);
  revalidatePath(`/meetings/${String(formData.get("meetingId") ?? "")}`);
}
export async function rejectProposalAction(formData: FormData) {
  await rejectProposal(String(formData.get("proposalId") ?? ""), REVIEWER);
  revalidatePath(`/meetings/${String(formData.get("meetingId") ?? "")}`);
}

// -------------------- Procedimiento --------------------
export async function generateProcedureAction(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  await generateProcedure(processId);
  revalidatePath(`/processes/${processId}/procedure`);
  redirect(`/processes/${processId}/procedure`);
}

// -------------------- Pendientes (CRUD manual) --------------------
export async function addActionItem(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  const description = String(formData.get("description") ?? "").trim();
  if (!processId || !description) return;
  await prisma.actionItem.create({
    data: { processId, description, owner: str(formData.get("owner")), dueDate: date(formData.get("dueDate")) },
  });
  revalidatePath(`/processes/${processId}`);
}
export async function updateActionItem(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  const data: Record<string, unknown> = {};
  if (formData.has("status")) data.status = String(formData.get("status"));
  if (formData.has("owner")) data.owner = str(formData.get("owner"));
  if (formData.has("description")) data.description = String(formData.get("description"));
  await prisma.actionItem.update({ where: { id }, data });
  revalidatePath(`/processes/${processId}`);
}
export async function deleteActionItem(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  await prisma.actionItem.delete({ where: { id } });
  revalidatePath(`/processes/${processId}`);
}

// -------------------- Decisiones (CRUD manual) --------------------
export async function addDecision(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  const statement = String(formData.get("statement") ?? "").trim();
  if (!processId || !statement) return;
  await prisma.decision.create({
    data: { processId, statement, rationale: str(formData.get("rationale")), owner: str(formData.get("owner")) },
  });
  revalidatePath(`/processes/${processId}`);
}
export async function deleteDecision(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  await prisma.decision.delete({ where: { id } });
  revalidatePath(`/processes/${processId}`);
}

// -------------------- Riesgos (CRUD manual) --------------------
export async function addRisk(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  const description = String(formData.get("description") ?? "").trim();
  if (!processId || !description) return;
  await prisma.risk.create({
    data: {
      processId,
      description,
      impact: String(formData.get("impact") ?? "medium"),
      mitigation: str(formData.get("mitigation")),
    },
  });
  revalidatePath(`/processes/${processId}`);
}
export async function updateRisk(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  const data: Record<string, unknown> = {};
  if (formData.has("status")) data.status = String(formData.get("status"));
  if (formData.has("mitigation")) data.mitigation = str(formData.get("mitigation"));
  await prisma.risk.update({ where: { id }, data });
  revalidatePath(`/processes/${processId}`);
}
export async function deleteRisk(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const processId = String(formData.get("processId") ?? "");
  await prisma.risk.delete({ where: { id } });
  revalidatePath(`/processes/${processId}`);
}

// -------------------- helpers --------------------
function str(v: FormDataEntryValue | null): string | null {
  const s = v ? String(v).trim() : "";
  return s.length ? s : null;
}
function date(v: FormDataEntryValue | null): Date | null {
  const s = v ? String(v).trim() : "";
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}
