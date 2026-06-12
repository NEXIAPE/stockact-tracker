/**
 * Adaptador genérico para APIs compatibles con OpenAI (Chat Completions).
 * Sirve para Groq, Google Gemini (endpoint OpenAI-compat), OpenRouter, etc.
 * Configurable por base URL + clave + modelo.
 */
import type { LlmPort, ExtractionContext, AuditContext } from "../port";
import { MeetingExtractionSchema, type MeetingExtraction } from "../../domain/extraction";
import { RecommendationDraftSchema, type RecommendationDraft } from "../../domain/recommendation";
import { SYSTEM_PROMPT, buildUserPrompt, AUDIT_SYSTEM_PROMPT, buildAuditPrompt } from "../prompts";
import { parseJsonLoose } from "../json";
import { z } from "zod";

const AuditResponseSchema = z.object({ recommendations: z.array(RecommendationDraftSchema).default([]) });

export class OpenAICompatAdapter implements LlmPort {
  constructor(
    public readonly name: string,
    private baseUrl: string,
    private apiKey: string,
    private model: string
  ) {}

  private async chat(system: string, user: string): Promise<string> {
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        temperature: 0.2,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
    });
    if (!res.ok) {
      throw new Error(`${this.name} API error ${res.status}: ${(await res.text()).slice(0, 500)}`);
    }
    const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> };
    return data.choices?.[0]?.message?.content ?? "{}";
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
