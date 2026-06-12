/**
 * Puerto de IA (hexagonal). El dominio depende SOLO de esta interfaz.
 * Los adaptadores concretos (Claude, Ollama, mock) la implementan.
 */
import type { MeetingExtraction } from "../domain/extraction";
import type { BpmnModel } from "../domain/bpmn";
import type { RecommendationDraft } from "../domain/recommendation";

export interface ExtractionContext {
  processName: string;
  processObjective?: string | null;
  /** Tipo de trabajo: new | improvement | owner_definition | normative. */
  processKind?: string;
  /** Modelo BPMN vigente, para que el LLM detecte CAMBIOS y no parta de cero. */
  currentBpmn: BpmnModel;
  /** Resúmenes de reuniones previas: memoria del "Proceso Vivo". */
  priorSummaries: string[];
}

export interface AuditContext {
  processName: string;
  processObjective?: string | null;
  processKind: string;
  currentBpmn: BpmnModel;
  decisions: string[];
  risks: string[];
}

export interface LlmPort {
  readonly name: string;
  /** Extrae minuta + artefactos + cambios BPMN + recomendaciones de una transcripción. */
  extractFromTranscript(
    transcript: string,
    ctx: ExtractionContext
  ): Promise<MeetingExtraction>;
  /**
   * Auditoría de consultor sobre el proceso consolidado: PROPONE gaps, controles,
   * actividades faltantes, riesgos no vistos. Devuelve [] si el adaptador no aplica IA.
   */
  auditProcess(ctx: AuditContext): Promise<RecommendationDraft[]>;
}
