from langchain_core.documents import Document

from app.query.answer import format_excerpts, parse_answer
from app.query.rerank import rerank
from app.query.rrf import rrf_merge


def doc(cid, text="t", **meta):
    return Document(page_content=text, metadata={"chunk_id": cid, **meta})


def test_rrf_rewards_agreement_across_lists():
    merged = rrf_merge([[doc("A"), doc("B")], [doc("C"), doc("X"), doc("A")]], k=60)
    assert [d.metadata["chunk_id"] for d in merged][:3] == ["A", "C", "B"]
    assert round(merged[0].metadata["rrf_score"], 4) == 0.0323


def test_build_trace_shape():
    from app.models.schemas import Rewrite
    from app.query.trace import build_trace

    meta = {"start_ts": 1790834400, "end_ts": 1790838000, "participants": "Riya, Amit Client"}
    top = [
        doc(1, "x" * 400, rerank_score=3.42, **meta),
        doc(2, "short", rerank_score=-9.1, **meta),
    ]
    state = {
        "rewrite": Rewrite(normalized="budget kitna", expansions=["total budget"], keywords=["b"]),
        "hits": {
            "queries": ["budget?", "budget kitna"],
            "vector": [[doc(1), doc(2), doc(3)], [doc(1)]],
            "fts": [doc(2), doc(4)],
            "fts_query": "budget? b",
        },
        "candidates": [doc(1), doc(2), doc(3), doc(4)],
        "top": {"docs": top, "best": 3.42},
    }
    t = build_trace(
        state,
        cited_ids={1},
        gated=False,
        min_relevance=-8.0,
        rerank_enabled=True,
        prompt_version="answer_v1",
        tz="Asia/Kolkata",
    )
    assert [q["vector_hits"] for q in t["retrieval"]["queries"]] == [3, 1]
    assert t["retrieval"]["fts_hits"] == 2 and t["retrieval"]["merged"] == 4
    assert t["retrieval"]["fts_query"] == "budget? b"
    assert [c["score"] for c in t["reranked"]] == [3.42, -9.1]
    assert [c["cited"] for c in t["reranked"]] == [True, False]
    assert len(t["reranked"][0]["preview"]) <= 160
    assert t["reranked"][0]["start_ts"].endswith("+05:30")
    assert t["best_score"] == 3.42 and t["gated"] is False and t["min_relevance"] == -8.0


def test_parse_answer_splits_sources_line():
    assert parse_answer("Delivery 15 Nov tak hogi.\nSOURCES: [2, 1]") == (
        "Delivery 15 Nov tak hogi.",
        [2, 1],
        False,
    )


def test_parse_answer_not_found():
    assert parse_answer("NOT_FOUND")[2] is True


def test_parse_answer_without_sources_line():
    assert parse_answer("Rahul ne bola tha.") == ("Rahul ne bola tha.", [], False)


def test_excerpts_are_numbered_and_delimited():
    out = format_excerpts(
        [doc(1, "[11:14] Amit: paisa 20 tarikh", start_ts=1790919840, participants="Amit")]
    )
    assert out.startswith('<excerpt id="1" date="02 Oct 2026" participants="Amit">\n')
    assert out.endswith("[11:14] Amit: paisa 20 tarikh\n</excerpt>")


class KeywordReranker:
    """Scores 0 if the query's last word appears in the passage, else -11."""

    def score(self, pairs):
        return [0.0 if q.split()[-1] in p else -11.0 for q, p in pairs]


def test_rerank_uses_best_score_across_query_variants():
    docs = [doc(1, "movie kal"), doc(2, "paisa 20 tarikh")]
    top, best = rerank(["payment kab", "kab paisa"], docs, KeywordReranker(), top_n=20, final_k=1)
    assert [d.metadata["chunk_id"] for d in top] == [2]
    assert best == 0.0


def test_rerank_disabled_passes_through():
    docs = [doc(1), doc(2), doc(3)]
    top, best = rerank(["q"], docs, None, top_n=20, final_k=2)
    assert [d.metadata["chunk_id"] for d in top] == [1, 2] and best is None
