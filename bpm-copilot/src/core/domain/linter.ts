/**
 * Linter de proceso (consultor determinista, SIN IA).
 *
 * Analiza el BPMN consolidado y el contexto del proceso para PROPONER gaps:
 * controles faltantes, actividades no mapeadas (rutas de rechazo/excepción),
 * owners sin definir, malas prácticas BPMN, falta de registros/evidencia, etc.
 *
 * Coste cero, siempre disponible. La IA (auditoría) lo complementa.
 */
import type { BpmnModel } from "./bpmn";
import type { RecommendationDraft } from "./recommendation";

export interface LintContext {
  kind: string; // new | improvement | owner_definition | normative
  riskCount: number;
  hasPolicies: boolean; // ¿hay decisiones/políticas registradas?
  hasOwnerStakeholder: boolean; // ¿hay algún stakeholder con cargo de jefatura?
}

const CONTROL_VERBS = /\b(valida|verifica|aprueba|autoriza|concilia|revisa|controla|coteja)/i;
const APPROVAL_VERBS = /\b(aprueba|autoriza|valida)/i;

export function lintProcess(bpmn: BpmnModel, ctx: LintContext): RecommendationDraft[] {
  const recs: RecommendationDraft[] = [];
  const acts = bpmn.activities;
  const hasFlows = bpmn.flows.length > 0;

  // --- Estructura BPMN ---
  if (!bpmn.events.some((e) => e.type === "start")) {
    recs.push({
      category: "best_practice",
      severity: "warning",
      title: "Falta evento de inicio",
      detail: "El flujo no tiene un evento de inicio explícito; dificulta saber qué dispara el proceso.",
      suggestion: "Define el evento que inicia el proceso (p.ej. recepción de solicitud/factura).",
    });
  }
  if (!bpmn.events.some((e) => e.type === "end")) {
    recs.push({
      category: "best_practice",
      severity: "info",
      title: "Falta evento de fin",
      detail: "No se identifica el cierre del proceso.",
      suggestion: "Define el evento de fin (p.ej. pago confirmado / caso cerrado).",
    });
  }

  // --- Owners / responsables ---
  const noRole = acts.filter((a) => !a.role || a.role.trim() === "");
  if (noRole.length) {
    const isOwnerFocus = ctx.kind === "owner_definition";
    recs.push({
      category: "owner",
      severity: isOwnerFocus ? "critical" : "warning",
      title: `${noRole.length} actividad(es) sin responsable asignado`,
      detail: `Sin responsable claro hay riesgo de tareas huérfanas: ${noRole.slice(0, 3).map((a) => `"${a.name}"`).join(", ")}${noRole.length > 3 ? "…" : ""}.`,
      suggestion: "Asigna un rol/área responsable (RACI) a cada actividad.",
    });
  }

  // --- Controles ---
  const hasControl = acts.some((a) => CONTROL_VERBS.test(a.name));
  if (acts.length >= 3 && !hasControl) {
    recs.push({
      category: "control",
      severity: "warning",
      title: "El proceso no contempla actividades de control",
      detail: "No se detectan validaciones, aprobaciones ni conciliaciones. Es un riesgo de calidad y cumplimiento.",
      suggestion: "Incorpora puntos de control (validación de datos, aprobación, conciliación) en pasos críticos.",
    });
  }
  // Aprobación sin política/umbral
  const approvals = acts.filter((a) => APPROVAL_VERBS.test(a.name));
  if (approvals.length && !ctx.hasPolicies) {
    recs.push({
      category: "control",
      severity: "warning",
      title: "Aprobaciones sin política o umbral definido",
      detail: `Hay actividades de aprobación (${approvals.map((a) => `"${a.name}"`).slice(0, 2).join(", ")}) pero no hay políticas/umbrales registrados que delimiten cuándo aplica cada nivel.`,
      suggestion: "Define umbrales de aprobación (montos, niveles) y registra la política como decisión.",
    });
  }

  // --- Rutas de excepción / rechazo ---
  if (hasFlows) {
    const outByNode = new Map<string, number>();
    for (const f of bpmn.flows) outByNode.set(f.from, (outByNode.get(f.from) ?? 0) + 1);
    const lonelyGateways = bpmn.gateways.filter((g) => (outByNode.get(g.id) ?? 0) < 2);
    if (lonelyGateways.length) {
      recs.push({
        category: "missing_activity",
        severity: "warning",
        title: "Gateways sin caminos alternativos (¿falta ruta de rechazo/excepción?)",
        detail: `Los gateways ${lonelyGateways.map((g) => `"${g.name}"`).slice(0, 2).join(", ")} tienen una sola salida; normalmente una decisión abre al menos dos caminos.`,
        suggestion: "Modela explícitamente el camino negativo (rechazo, devolución, excepción) y su tratamiento.",
      });
    }
    // Actividades desconectadas
    const referenced = new Set<string>();
    for (const f of bpmn.flows) { referenced.add(f.from); referenced.add(f.to); }
    const dangling = acts.filter((a) => !referenced.has(a.id));
    if (dangling.length) {
      recs.push({
        category: "best_practice",
        severity: "info",
        title: `${dangling.length} actividad(es) desconectada(s) del flujo`,
        detail: `No tienen flujos de entrada/salida: ${dangling.slice(0, 3).map((a) => `"${a.name}"`).join(", ")}.`,
        suggestion: "Conecta estas actividades al flujo o elimínalas si ya no aplican.",
      });
    }
  }

  // --- Registros / evidencia (trazabilidad) ---
  const noOutputs = acts.filter((a) => a.outputs.length === 0);
  if (acts.length && noOutputs.length === acts.length) {
    recs.push({
      category: "data",
      severity: "info",
      title: "Ninguna actividad registra evidencia/salida",
      detail: "Sin registros (correo, guía, reporte, sistema) el proceso no es auditable.",
      suggestion: "Para cada actividad clave define el registro/evidencia que produce (columna Registros del procedimiento).",
    });
  }

  // --- Riesgos ---
  if (ctx.riskCount === 0 && acts.length >= 2) {
    recs.push({
      category: "risk",
      severity: "info",
      title: "No se han identificado riesgos del proceso",
      detail: "Todo proceso tiene riesgos; no tenerlos mapeados impide diseñar controles.",
      suggestion: "Realiza un breve análisis de riesgos (qué puede fallar en cada paso) y registra mitigaciones.",
    });
  }

  // --- Énfasis según tipo de trabajo ---
  if (ctx.kind === "improvement" && acts.length) {
    recs.push({
      category: "efficiency",
      severity: "info",
      title: "Oportunidades de mejora a evaluar",
      detail: "Al ser un proceso a mejorar, conviene buscar reprocesos, actividades manuales sin sistema y handoffs innecesarios.",
      suggestion: "Identifica actividades manuales candidatas a automatización y pasos que no agregan valor.",
    });
  }
  if (ctx.kind === "normative" && noOutputs.length) {
    recs.push({
      category: "compliance",
      severity: "warning",
      title: "Evidencia de cumplimiento insuficiente",
      detail: "En un proceso normativo cada control debe dejar evidencia verificable.",
      suggestion: "Asegura que cada requisito regulatorio tenga una actividad con su registro/evidencia asociada.",
    });
  }
  if (ctx.kind === "owner_definition" && !ctx.hasOwnerStakeholder) {
    recs.push({
      category: "owner",
      severity: "critical",
      title: "Owner del proceso sin definir",
      detail: "El objetivo es definir owners y no se identifica un responsable de jefatura/gerencia entre los stakeholders.",
      suggestion: "Designa formalmente al owner del proceso y los responsables por sub-proceso.",
    });
  }

  return recs;
}
