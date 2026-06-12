/**
 * Recomendación del consultor: una PROPUESTA proactiva (no algo dicho en la
 * reunión, sino algo que el sistema sugiere que falta o conviene revisar).
 */
import { z } from "zod";

export const RECOMMENDATION_CATEGORIES = [
  "control",
  "missing_activity",
  "risk",
  "best_practice",
  "owner",
  "efficiency",
  "data",
  "compliance",
] as const;

export const RecommendationDraftSchema = z.object({
  category: z.enum(RECOMMENDATION_CATEGORIES).default("best_practice"),
  severity: z.enum(["info", "warning", "critical"]).default("warning"),
  title: z.string(),
  detail: z.string().nullish(),
  suggestion: z.string().nullish(),
});

export type RecommendationDraft = z.infer<typeof RecommendationDraftSchema>;

export const CATEGORY_LABEL: Record<string, string> = {
  control: "Control",
  missing_activity: "Actividad faltante",
  risk: "Riesgo",
  best_practice: "Buena práctica BPMN",
  owner: "Owner / Responsable",
  efficiency: "Eficiencia",
  data: "Datos / Registros",
  compliance: "Cumplimiento",
};
