"""What the ask chain did, for the web inspector. Built from chain state; never logged (TRD §10)."""

from datetime import datetime
from zoneinfo import ZoneInfo

PREVIEW_CHARS = 160


def build_trace(
    state: dict,
    *,
    cited_ids: set[int],
    gated: bool,
    min_relevance: float,
    rerank_enabled: bool,
    prompt_version: str,
    tz: str,
) -> dict:
    zone = ZoneInfo(tz)
    hits = state["hits"]

    def iso(epoch: int) -> str:
        return datetime.fromtimestamp(epoch, zone).isoformat()

    return {
        "rewrite": state["rewrite"],
        "retrieval": {
            "queries": [
                {"text": q, "vector_hits": len(docs)}
                for q, docs in zip(hits["queries"], hits["vector"], strict=True)
            ],
            "fts_query": hits["fts_query"],
            "fts_hits": len(hits["fts"]),
            "merged": len(state["candidates"]),
        },
        "reranked": [
            {
                "chunk_id": d.metadata["chunk_id"],
                "start_ts": iso(d.metadata["start_ts"]),
                "end_ts": iso(d.metadata["end_ts"]),
                "participants": d.metadata["participants"],
                "score": d.metadata.get("rerank_score"),
                "preview": d.page_content[:PREVIEW_CHARS],
                "cited": d.metadata["chunk_id"] in cited_ids,
            }
            for d in state["top"]["docs"]
        ],
        "best_score": state["top"]["best"],
        "min_relevance": min_relevance,
        "gated": gated,
        "rerank_enabled": rerank_enabled,
        "prompt_version": prompt_version,
    }
