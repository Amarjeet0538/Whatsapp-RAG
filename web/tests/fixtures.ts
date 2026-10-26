import type { AskResponse, Trace } from "../src/types";
import type { Turn } from "../src/thread";

export function trace(over: Partial<Trace> = {}): Trace {
  return {
    rewrite: { normalized: "budget kitna approved", expansions: ["total budget"], keywords: ["budget"] },
    retrieval: {
      queries: [{ text: "total budget kitna approved hai?", vector_hits: 8 }],
      fts_query: "total budget kitna approved hai? budget",
      fts_hits: 5,
      merged: 10,
    },
    reranked: [
      {
        chunk_id: 31,
        start_ts: "2026-10-03T10:00:00+05:30",
        end_ts: "2026-10-03T10:20:00+05:30",
        participants: "Riya, Amit Client",
        score: 3.42,
        preview: "Budget 25000 tak approved hai",
        cited: true,
      },
    ],
    best_score: 3.42,
    min_relevance: -8,
    gated: false,
    rerank_enabled: true,
    prompt_version: "answer_v1",
    latency_ms: 2140,
    ...over,
  };
}

export function response(over: Partial<AskResponse> = {}): AskResponse {
  return {
    answer: "Budget 25000 approved [1]",
    found: true,
    interpreted_range: null,
    sources: [
      {
        message_id: 812,
        excerpt: 1,
        sender: "Amit Client",
        ts: "2026-10-03T10:12:00+05:30",
        snippet: "Budget 25000 tak approved hai",
      },
    ],
    latency_ms: 2140,
    trace: trace(),
    ...over,
  };
}

export function turn(over: Partial<Turn> = {}): Turn {
  return {
    id: "t1",
    question: "total budget kitna approved hai?",
    askedAs: "Riya",
    status: "done",
    response: response(),
    startedAt: 0,
    ...over,
  };
}
