"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { processMeeting } from "@/core/ingest/pipeline";
import { approveProposal, rejectProposal } from "@/core/ingest/proposals";

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

// -------------------- Reuniones --------------------
export async function createMeeting(formData: FormData) {
  const processId = String(formData.get("processId") ?? "");
  const title = str(formData.get("title"));
  const transcript = str(formData.get("transcript"));
  if (!processId) return;
  const meeting = await prisma.meeting.create({
    data: {
      processId,
      title,
      transcript,
      date: date(formData.get("date")) ?? new Date(),
    },
  });
  revalidatePath(`/processes/${processId}`);
  redirect(`/meetings/${meeting.id}`);
}

export async function processMeetingAction(formData: FormData) {
  const meetingId = String(formData.get("meetingId") ?? "");
  if (!meetingId) return;
  await processMeeting(meetingId);
  revalidatePath(`/meetings/${meetingId}`);
}

// -------------------- Propuestas (human-in-the-loop) --------------------
export async function approveProposalAction(formData: FormData) {
  const id = String(formData.get("proposalId") ?? "");
  const meetingId = String(formData.get("meetingId") ?? "");
  await approveProposal(id, REVIEWER);
  revalidatePath(`/meetings/${meetingId}`);
}
export async function rejectProposalAction(formData: FormData) {
  const id = String(formData.get("proposalId") ?? "");
  const meetingId = String(formData.get("meetingId") ?? "");
  await rejectProposal(id, REVIEWER);
  revalidatePath(`/meetings/${meetingId}`);
}

// -------------------- Artefactos: cambios de estado --------------------
export async function updateActionItemStatus(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const status = String(formData.get("status") ?? "");
  const processId = String(formData.get("processId") ?? "");
  await prisma.actionItem.update({ where: { id }, data: { status } });
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
