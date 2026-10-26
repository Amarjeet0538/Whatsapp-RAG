export type Segment = { kind: "text"; text: string } | { kind: "cite"; n: number };

/**
 * Split answer text on [n] markers. [n] names the excerpt the LLM read, so it is a citation
 * only if some source came from excerpt n (`excerpts`); other markers stay as plain text.
 */
export function splitCitations(answer: string, excerpts: number[]): Segment[] {
  const valid = new Set(excerpts);
  const out: Segment[] = [];
  let buf = "";
  let last = 0;
  for (const m of answer.matchAll(/\[(\d+)\]/g)) {
    const n = Number(m[1]);
    const end = m.index + m[0].length;
    if (!valid.has(n)) {
      buf += answer.slice(last, end);
    } else {
      buf += answer.slice(last, m.index);
      if (buf) out.push({ kind: "text", text: buf });
      buf = "";
      out.push({ kind: "cite", n });
    }
    last = end;
  }
  buf += answer.slice(last);
  if (buf) out.push({ kind: "text", text: buf });
  return out;
}
