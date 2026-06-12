/**
 * Representación BPMN interna (propia, simplificada).
 *
 * Objetivo: una representación estructurada y versionable del flujo, suficiente
 * para (a) razonar sobre el proceso y (b) exportar a Mermaid / BPMN-XML / PlantUML.
 * NO busca paridad 1:1 con el estándar BPMN 2.0 en el MVP.
 */
import { z } from "zod";

export const BpmnEventSchema = z.object({
  id: z.string(),
  type: z.enum(["start", "end", "intermediate"]),
  name: z.string(),
});

export const BpmnActivitySchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.enum(["task", "user_task", "service_task", "manual_task", "subprocess"]).default("task"),
  role: z.string().nullish(), // lane / responsable
  system: z.string().nullish(), // sistema que soporta la actividad
  inputs: z.array(z.string()).default([]),
  outputs: z.array(z.string()).default([]),
});

export const BpmnGatewaySchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.enum(["exclusive", "parallel", "inclusive", "event_based"]).default("exclusive"),
});

export const BpmnFlowSchema = z.object({
  id: z.string(),
  from: z.string(), // id de evento/actividad/gateway
  to: z.string(),
  condition: z.string().nullish(), // etiqueta para flujos condicionales
});

export const BpmnModelSchema = z.object({
  events: z.array(BpmnEventSchema).default([]),
  activities: z.array(BpmnActivitySchema).default([]),
  gateways: z.array(BpmnGatewaySchema).default([]),
  flows: z.array(BpmnFlowSchema).default([]),
  roles: z.array(z.string()).default([]),
  systems: z.array(z.string()).default([]),
  dataObjects: z.array(z.string()).default([]),
});

export type BpmnEvent = z.infer<typeof BpmnEventSchema>;
export type BpmnActivity = z.infer<typeof BpmnActivitySchema>;
export type BpmnGateway = z.infer<typeof BpmnGatewaySchema>;
export type BpmnFlow = z.infer<typeof BpmnFlowSchema>;
export type BpmnModel = z.infer<typeof BpmnModelSchema>;

export function emptyBpmnModel(): BpmnModel {
  return {
    events: [],
    activities: [],
    gateways: [],
    flows: [],
    roles: [],
    systems: [],
    dataObjects: [],
  };
}

/** Nodo "navegable" por id (evento | actividad | gateway). */
export function nodeLabel(model: BpmnModel, id: string): string {
  return (
    model.events.find((e) => e.id === id)?.name ??
    model.activities.find((a) => a.id === id)?.name ??
    model.gateways.find((g) => g.id === id)?.name ??
    id
  );
}
