// Mirrors api/app/models/schemas.py. Field names stay snake_case, as the API returns them.

export interface GroupSummary {
  wa_group_id: string;
  name: string | null;
  message_count: number;
  member_count: number;
  last_message_ts: string | null;
}

export interface MemberSummary {
  display_name: string;
  message_count: number;
}

export interface ImportResponse {
  group_id: number;
  new_messages: number;
  chunks: number;
}

export interface Source {
  message_id: number;
  excerpt: number;
  sender: string | null;
  ts: string;
  snippet: string;
}

export interface Rewrite {
  normalized: string;
  expansions: string[];
  keywords: string[];
}

export interface TraceChunk {
  chunk_id: number;
  start_ts: string;
  end_ts: string;
  participants: string;
  score: number | null;
  preview: string;
  cited: boolean;
}

export interface Trace {
  rewrite: Rewrite;
  retrieval: {
    queries: { text: string; vector_hits: number }[];
    fts_query: string;
    fts_hits: number;
    merged: number;
  };
  reranked: TraceChunk[];
  best_score: number | null;
  min_relevance: number;
  gated: boolean;
  rerank_enabled: boolean;
  prompt_version: string;
  latency_ms: number;
}

export interface AskResponse {
  answer: string;
  found: boolean;
  interpreted_range: Record<string, unknown> | null;
  sources: Source[];
  latency_ms: number;
  trace: Trace;
}

export interface ContextMessage {
  id: number;
  sender: string | null;
  ts: string;
  text: string;
  is_target: boolean;
}

export interface ContextResponse {
  target_id: number;
  messages: ContextMessage[];
}
