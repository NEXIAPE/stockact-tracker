/**
 * Adaptador Ollama (modelo local, gratis). Para usuarios que priorizan coste
 * cero / privacidad total. Requiere `ollama serve` y un modelo instruct.
 */
import type { LlmPort, ExtractionContext } from "../port";
import { MeetingExtractionSchema, type MeetingExtraction } from "../../domain/extraction";
import { SYSTEM_PROMPT, buildUserPrompt } from "../prompts";
import { parseJsonLoose } from "../json";

export class OllamaAdapter implements LlmPort {
  readonly name = "ollama";
  constructor(
    private baseUrl: string = "http://localhost:11434",
    private model: string = "qwen2.5:7b-instruct"
  ) {}

  async extractFromTranscript(
    transcript: string,
    ctx: ExtractionContext
  ): Promise<MeetingExtraction> {
    const res = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model: this.model,
        stream: false,
        format: "json",
        options: { temperature: 0.2 },
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: buildUserPrompt(transcript, ctx) },
        ],
      }),
    });

    if (!res.ok) {
      throw new Error(`Ollama error ${res.status}: ${await res.text()}`);
    }

    const data = (await res.json()) as { message?: { content?: string } };
    const raw = parseJsonLoose(data.message?.content ?? "{}");
    return MeetingExtractionSchema.parse(raw);
  }
}
