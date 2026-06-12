/**
 * Factory del puerto LLM. Selecciona el adaptador por env (LLM_PROVIDER) con
 * FALLBACK seguro a "mock" para que la app SIEMPRE sea ejecutable sin coste.
 */
import type { LlmPort } from "./port";
import { ClaudeAdapter } from "./adapters/claude";
import { OllamaAdapter } from "./adapters/ollama";
import { OpenAICompatAdapter } from "./adapters/openai-compat";
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

  // Groq — gratis (Llama 3.3 70B u otros), API compatible con OpenAI.
  if (provider === "groq") {
    const key = process.env.GROQ_API_KEY;
    if (!key) {
      console.warn("[bpm-copilot] LLM_PROVIDER=groq sin GROQ_API_KEY. Usando mock.");
      return new MockAdapter();
    }
    return new OpenAICompatAdapter(
      "groq",
      "https://api.groq.com/openai/v1",
      key,
      process.env.GROQ_MODEL ?? "llama-3.3-70b-versatile"
    );
  }

  // Google Gemini — capa gratis, vía su endpoint compatible con OpenAI.
  if (provider === "gemini") {
    const key = process.env.GEMINI_API_KEY;
    if (!key) {
      console.warn("[bpm-copilot] LLM_PROVIDER=gemini sin GEMINI_API_KEY. Usando mock.");
      return new MockAdapter();
    }
    return new OpenAICompatAdapter(
      "gemini",
      "https://generativelanguage.googleapis.com/v1beta/openai",
      key,
      process.env.GEMINI_MODEL ?? "gemini-2.0-flash"
    );
  }

  if (provider === "ollama") {
    return new OllamaAdapter(process.env.OLLAMA_BASE_URL, process.env.OLLAMA_MODEL);
  }

  return new MockAdapter();
}
