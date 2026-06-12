/**
 * Esquema del resultado de procesar una transcripción.
 *
 * Es el "contrato" que TODO adaptador de IA (Claude, Ollama, mock) debe cumplir.
 * Mantenerlo estable desacopla el dominio del proveedor de IA (principio
 * de arquitectura agnóstica).
 */
import { z } from "zod";
import { BpmnModelSchema } from "./bpmn";

export const ExtractedAgreementSchema = z.object({
  text: z.string(),
});

export const ExtractedActionItemSchema = z.object({
  description: z.string(),
  owner: z.string().nullish(),
  dueDate: z.string().nullish(), // ISO date si se detecta
});

export const ExtractedDecisionSchema = z.object({
  statement: z.string(),
  rationale: z.string().nullish(),
  owner: z.string().nullish(),
});

export const ExtractedRiskSchema = z.object({
  description: z.string(),
  impact: z.enum(["low", "medium", "high"]).default("medium"),
  likelihood: z.enum(["low", "medium", "high"]).default("medium"),
  mitigation: z.string().nullish(),
});

/** Cambio propuesto sobre el modelo BPMN vigente (human-in-the-loop). */
export const ExtractedBpmnChangeSchema = z.object({
  action: z.enum(["add", "update", "remove"]),
  title: z.string(),
  detail: z.string().nullish(),
  // Fragmento BPMN afectado (parcial). El motor de diff lo reconcilia.
  fragment: BpmnModelSchema.partial().default({}),
});

export const MeetingExtractionSchema = z.object({
  summary: z.string(),
  participants: z.array(z.string()).default([]),
  agreements: z.array(ExtractedAgreementSchema).default([]),
  actionItems: z.array(ExtractedActionItemSchema).default([]),
  decisions: z.array(ExtractedDecisionSchema).default([]),
  risks: z.array(ExtractedRiskSchema).default([]),
  bpmnChanges: z.array(ExtractedBpmnChangeSchema).default([]),
});

export type MeetingExtraction = z.infer<typeof MeetingExtractionSchema>;
export type ExtractedActionItem = z.infer<typeof ExtractedActionItemSchema>;
export type ExtractedDecision = z.infer<typeof ExtractedDecisionSchema>;
export type ExtractedRisk = z.infer<typeof ExtractedRiskSchema>;
export type ExtractedBpmnChange = z.infer<typeof ExtractedBpmnChangeSchema>;
