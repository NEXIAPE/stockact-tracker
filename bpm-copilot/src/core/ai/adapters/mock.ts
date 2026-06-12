/**
 * Adaptador Mock — extracción heurística determinista, SIN IA ni red.
 *
 * Propósito: que la app sea ejecutable y demostrable a coste cero (CI, demos,
 * desarrollo offline) y como fallback si no hay clave de Claude configurada.
 * No pretende calidad de LLM: aplica reglas simples sobre la transcripción.
 */
import type { LlmPort, ExtractionContext } from "../port";
import type { MeetingExtraction } from "../../domain/extraction";

// Nota: heurísticas por PREFIJO (sin \b final) para capturar conjugaciones
// (p.ej. "decid" -> "decidimos", "decidió"). Calidad deliberadamente básica.
const ACTION_HINTS = /\b(pendiente|tarea|queda|deber|debe|enviar|prepar|revis|coordin|seguimiento|acci[óo]n)/i;
const DECISION_HINTS = /\b(decid|decisi[óo]n|se aprueba|se opta|optamos|definimos|se define|resoluci[óo]n)/i;
const AGREEMENT_HINTS = /\b(acordamos|acuerdo|de acuerdo|consenso|confirmamos|validamos)/i;
const RISK_HINTS = /\b(riesgo|problema|amenaza|bloqueo|impedimento|peligro|retraso|se pierde|se pierden)/i;
const ACTIVITY_HINTS = /\b(registra|valida|aprueba|env[íi]a|revisa|genera|emite|crea|notifica|gestiona|programa|procesa)/i;

function sentences(text: string): string[] {
  return text
    .replace(/\r/g, "")
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 12);
}

function detectOwner(s: string): string | null {
  // "Juan enviará...", "@Maria", "Responsable: Pedro"
  const at = s.match(/@(\w[\wáéíóúñ]+)/i);
  if (at) return at[1];
  const resp = s.match(/responsable[:\s]+([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)/i);
  if (resp) return resp[1];
  const name = s.match(/\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+(?:enviar|prepar|revis|coordin|har|deber)/);
  if (name) return name[1];
  return null;
}

function detectParticipants(text: string): string[] {
  // Líneas tipo "Juan Pérez:" al inicio (formato típico de transcripción Teams)
  const set = new Set<string>();
  for (const line of text.split(/\n/)) {
    const m = line.match(/^\s*([A-ZÁÉÍÓÚÑ][\wáéíóúñ.]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ.]+)?)\s*:/);
    if (m && m[1].length < 40) set.add(m[1].trim());
  }
  return [...set].slice(0, 20);
}

export class MockAdapter implements LlmPort {
  readonly name = "mock";

  async extractFromTranscript(
    transcript: string,
    ctx: ExtractionContext
  ): Promise<MeetingExtraction> {
    const ss = sentences(transcript);

    const agreements = ss.filter((s) => AGREEMENT_HINTS.test(s)).slice(0, 10).map((text) => ({ text }));
    const decisions = ss
      .filter((s) => DECISION_HINTS.test(s))
      .slice(0, 10)
      .map((s) => ({ statement: s, rationale: null, owner: detectOwner(s) }));
    const actionItems = ss
      .filter((s) => ACTION_HINTS.test(s) && !DECISION_HINTS.test(s))
      .slice(0, 15)
      .map((s) => ({ description: s, owner: detectOwner(s), dueDate: null }));
    const risks = ss
      .filter((s) => RISK_HINTS.test(s))
      .slice(0, 10)
      .map((s) => ({
        description: s,
        impact: "medium" as const,
        likelihood: "medium" as const,
        mitigation: null,
      }));

    // BPMN: propone actividades a partir de frases con verbos de proceso que no
    // existan ya en el modelo vigente (deltas).
    const existing = new Set(ctx.currentBpmn.activities.map((a) => a.name.toLowerCase()));
    const candidates = ss.filter((s) => ACTIVITY_HINTS.test(s) && s.length < 140).slice(0, 8);
    const bpmnChanges = candidates
      .filter((s) => !existing.has(s.toLowerCase()))
      .slice(0, 5)
      .map((s, i) => ({
        action: "add" as const,
        title: `Posible actividad: ${s.slice(0, 60)}`,
        detail: s,
        fragment: {
          activities: [
            {
              id: `act_mock_${Date.now()}_${i}`,
              name: s.slice(0, 80),
              type: "task" as const,
              role: detectOwner(s),
              system: null,
              inputs: [],
              outputs: [],
            },
          ],
        },
      }));

    const participants = detectParticipants(transcript);
    const summary =
      `Reunión sobre "${ctx.processName}". Se identificaron ${agreements.length} acuerdo(s), ` +
      `${decisions.length} decisión(es), ${actionItems.length} pendiente(s) y ${risks.length} riesgo(s). ` +
      `(Extracción heurística sin IA — configura LLM_PROVIDER=claude para análisis completo.)`;

    return {
      summary,
      participants,
      agreements,
      actionItems,
      decisions,
      risks,
      bpmnChanges,
    };
  }
}
