/**
 * Adaptador Ollama (modelo local, gratis). Para usuarios que priorizan coste
 * cero / privacidad total. Requiere `ollama serve` y un modelo instruct.
 */
import type { LlmPort, ExtractionContext, AuditContext } from "../port";
import { MeetingExtractionSchema, type MeetingExtraction } from "../../domain/extraction";
import { RecommendationDraftSchema, type RecommendationDraft } from "../../domain/recommendation";
import { SYSTEM_PROMPT, buildUserPrompt, AUDIT_SYSTEM_PROMPT, buildAuditPrompt } from "../prompts";
import { parseJsonLoose } from "../json";
import { z } from "zod";

const AuditResponseSchema = z.object({ recommendations: z.array(RecommendationDraftSchema).default([]) });

export class OllamaAdapter implements LlmPort {
  readonly name = "ollama";
  constructor(
    private baseUrl: string = "http://localhost:11434",
    private model: string = "qwen2.5:7b-instruct"
  ) {}

  private async chat(system: string, user: string): Promise<string> {
    const res = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model: this.model,
        stream: false,
        format: "json",
        options: { temperature: 0.2 },
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
    });
    if (!res.ok) throw new Error(`Ollama error ${res.status}: ${await res.text()}`);
    const data = (await res.json()) as { message?: { content?: string } };
    return data.message?.content ?? "{}";
  }

  async extractFromTranscript(transcript: string, ctx: ExtractionContext): Promise<MeetingExtraction> {
    const text = await this.chat(SYSTEM_PROMPT, buildUserPrompt(transcript, ctx));
    return MeetingExtractionSchema.parse(parseJsonLoose(text));
  }

  async auditProcess(ctx: AuditContext): Promise<RecommendationDraft[]> {
    const text = await this.chat(AUDIT_SYSTEM_PROMPT, buildAuditPrompt(ctx));
    return AuditResponseSchema.parse(parseJsonLoose(text)).recommendations;
  }
}
