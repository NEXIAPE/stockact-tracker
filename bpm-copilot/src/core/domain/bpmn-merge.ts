/**
 * Motor de merge BPMN: aplica un fragmento (delta) aprobado sobre el modelo
 * vigente y produce un modelo nuevo. Base del versionado del "Proceso Vivo".
 */
import { BpmnModelSchema, type BpmnModel } from "./bpmn";

type Fragment = Partial<BpmnModel>;

function upsertById<T extends { id: string }>(list: T[], items: T[]): T[] {
  const map = new Map(list.map((x) => [x.id, x]));
  for (const it of items) map.set(it.id, { ...map.get(it.id), ...it });
  return [...map.values()];
}
function uniq(list: string[], items: string[]): string[] {
  return [...new Set([...list, ...items])];
}

export function applyFragment(
  current: BpmnModel,
  action: "add" | "update" | "remove",
  fragment: Fragment
): BpmnModel {
  const base = BpmnModelSchema.parse(current);
  const f = BpmnModelSchema.partial().parse(fragment);

  if (action === "remove") {
    const ids = new Set<string>([
      ...(f.events ?? []).map((x) => x.id),
      ...(f.activities ?? []).map((x) => x.id),
      ...(f.gateways ?? []).map((x) => x.id),
    ]);
    return BpmnModelSchema.parse({
      events: base.events.filter((x) => !ids.has(x.id)),
      activities: base.activities.filter((x) => !ids.has(x.id)),
      gateways: base.gateways.filter((x) => !ids.has(x.id)),
      flows: base.flows.filter((x) => !ids.has(x.from) && !ids.has(x.to)),
      roles: base.roles,
      systems: base.systems,
      dataObjects: base.dataObjects,
    });
  }

  // add | update -> upsert
  return BpmnModelSchema.parse({
    events: upsertById(base.events, f.events ?? []),
    activities: upsertById(base.activities, f.activities ?? []),
    gateways: upsertById(base.gateways, f.gateways ?? []),
    flows: upsertById(base.flows, f.flows ?? []),
    roles: uniq(base.roles, f.roles ?? []),
    systems: uniq(base.systems, f.systems ?? []),
    dataObjects: uniq(base.dataObjects, f.dataObjects ?? []),
  });
}
