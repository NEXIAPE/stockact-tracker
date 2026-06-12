/**
 * Puerto de IA (hexagonal). El dominio depende SOLO de esta interfaz.
 * Los adaptadores concretos (Claude, Ollama, mock) la implementan.
 */
import type { MeetingExtraction } from "../domain/extraction";
import type { BpmnModel } from "../domain/bpmn";

export interface ExtractionContext {
  processName: string;
  processObjective?: string | null;
  /** Modelo BPMN vigente, para que el LLM detecte CAMBIOS y no parta de cero. */
  currentBpmn: BpmnModel;
  /** Resúmenes de reuniones previas: memoria del "Proceso Vivo". */
  priorSummaries: string[];
}

export interface LlmPort {
  readonly name: string;
  /** Extrae minuta + artefactos + cambios BPMN propuestos de una transcripción. */
  extractFromTranscript(
    transcript: string,
    ctx: ExtractionContext
  ): Promise<MeetingExtraction>;
}
