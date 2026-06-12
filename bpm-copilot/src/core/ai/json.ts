/** Parseo tolerante de JSON devuelto por un LLM (puede venir con ```json fences). */
export function parseJsonLoose(text: string): unknown {
  const cleaned = text
    .trim()
    .replace(/^```(?:json)?/i, "")
    .replace(/```$/i, "")
    .trim();
  try {
    return JSON.parse(cleaned);
  } catch {
    // Intenta recortar al primer { ... último }
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start >= 0 && end > start) {
      return JSON.parse(cleaned.slice(start, end + 1));
    }
    throw new Error("No se pudo parsear JSON de la respuesta del modelo.");
  }
}
