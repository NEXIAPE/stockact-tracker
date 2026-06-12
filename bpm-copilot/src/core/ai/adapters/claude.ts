/**
 * Adaptador Claude (Anthropic). Default del MVP.
 * Usa la Messages API vía fetch (sin SDK para mantener deps mínimas).
 */
import type { LlmPort, ExtractionContext, AuditContext } from "../port";
import { MeetingExtractionSchema, type MeetingExtraction } from "../../domain/extraction";
import { RecommendationDraftSchema, type RecommendationDraft } from "../../domain/recommendation";
import { SYSTEM_PROMPT, buildUserPrompt, AUDIT_SYSTEM_PROMPT, buildAuditPrompt } from "../prompts";
import { parseJsonLoose } from "../json";
import { z } from "zod";

const API_URL = "https://api.anthropic.com/v1/messages";
const AuditResponseSchema = z.object({ recommendations: z.array(RecommendationDraftSchema).default([]) });

export class ClaudeAdapter implements LlmPort {
  readonly name = "claude";
  constructor(
    private apiKey: string,
    private model: string = "claude-sonnet-4-6"
  ) {}

  private async complete(system: string, user: string, maxTokens = 4096): Promise<string> {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": this.apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: this.model,
        max_tokens: maxTokens,
        system,
        messages: [{ role: "user", content: user }],
      }),
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Claude API error ${res.status}: ${body.slice(0, 500)}`);
    }
    const data = (await res.json()) as { content?: Array<{ type: string; text?: string }> };
    return (data.content ?? [])
      .filter((b) => b.type === "text")
      .map((b) => b.text ?? "")
      .join("\n");
  }

  async extractFromTranscript(transcript: string, ctx: ExtractionContext): Promise<MeetingExtraction> {
    const text = await this.complete(SYSTEM_PROMPT, buildUserPrompt(transcript, ctx));
    return MeetingExtractionSchema.parse(parseJsonLoose(text));
  }

  async auditProcess(ctx: AuditContext): Promise<RecommendationDraft[]> {
    const text = await this.complete(AUDIT_SYSTEM_PROMPT, buildAuditPrompt(ctx), 2048);
    return AuditResponseSchema.parse(parseJsonLoose(text)).recommendations;
  }
}
