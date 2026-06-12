/**
 * Factory del puerto LLM. Selecciona el adaptador por env (LLM_PROVIDER) con
 * FALLBACK seguro a "mock" para que la app SIEMPRE sea ejecutable sin coste.
 */
import type { LlmPort } from "./port";
import { ClaudeAdapter } from "./adapters/claude";
import { OllamaAdapter } from "./adapters/ollama";
import { MockAdapter } from "./adapters/mock";

export function getLlm(): LlmPort {
  const provider = (process.env.LLM_PROVIDER ?? "claude").toLowerCase();

  if (provider === "claude") {
    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) {
      // Sin clave -> degradación elegante a mock (no rompe la app).
      console.warn(
        "[bpm-copilot] LLM_PROVIDER=claude pero ANTHROPIC_API_KEY no está definida. Usando adaptador mock."
      );
      return new MockAdapter();
    }
    return new ClaudeAdapter(key, process.env.ANTHROPIC_MODEL ?? "claude-sonnet-4-6");
  }

  if (provider === "ollama") {
    return new OllamaAdapter(process.env.OLLAMA_BASE_URL, process.env.OLLAMA_MODEL);
  }

  return new MockAdapter();
}
