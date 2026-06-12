/**
 * Adaptador Claude (Anthropic). Default del MVP.
 * Usa la Messages API vía fetch (sin SDK para mantener deps mínimas).
 */
import type { LlmPort, ExtractionContext } from "../port";
import { MeetingExtractionSchema, type MeetingExtraction } from "../../domain/extraction";
import { SYSTEM_PROMPT, buildUserPrompt } from "../prompts";
import { parseJsonLoose } from "../json";

const API_URL = "https://api.anthropic.com/v1/messages";

export class ClaudeAdapter implements LlmPort {
  readonly name = "claude";
  constructor(
    private apiKey: string,
    private model: string = "claude-sonnet-4-6"
  ) {}

  async extractFromTranscript(
    transcript: string,
    ctx: ExtractionContext
  ): Promise<MeetingExtraction> {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": this.apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: this.model,
        max_tokens: 4096,
        system: SYSTEM_PROMPT,
        messages: [{ role: "user", content: buildUserPrompt(transcript, ctx) }],
      }),
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Claude API error ${res.status}: ${body.slice(0, 500)}`);
    }

    const data = (await res.json()) as { content?: Array<{ type: string; text?: string }> };
    const text = (data.content ?? [])
      .filter((b) => b.type === "text")
      .map((b) => b.text ?? "")
      .join("\n");

    const raw = parseJsonLoose(text);
    return MeetingExtractionSchema.parse(raw);
  }
}
