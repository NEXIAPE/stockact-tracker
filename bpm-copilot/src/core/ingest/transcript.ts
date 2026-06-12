/**
 * Normaliza texto de transcripción importado desde archivo.
 * Soporta texto plano y WebVTT (.vtt) / SRT (limpia timestamps y cues).
 */
export function normalizeTranscript(raw: string): string {
  const text = raw.replace(/\r/g, "");
  const looksVtt = /^WEBVTT/.test(text) || /\d{2}:\d{2}:\d{2}[.,]\d{3}\s+-->/.test(text);
  if (!looksVtt) return text.trim();

  const lines = text.split("\n");
  const out: string[] = [];
  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;
    if (t === "WEBVTT") continue;
    if (/^\d+$/.test(t)) continue; // índice de cue (SRT)
    if (/-->/.test(t)) continue; // línea de tiempos
    if (/^(NOTE|STYLE|REGION)\b/.test(t)) continue;
    // limpia tags inline tipo <v Nombre> o <00:00:00.000>
    out.push(t.replace(/<[^>]+>/g, "").trim());
  }
  // colapsa líneas repetidas consecutivas (común en captions en vivo)
  const dedup: string[] = [];
  for (const l of out) if (dedup[dedup.length - 1] !== l) dedup.push(l);
  return dedup.join("\n").trim();
}
