"""The ask pipeline as one LCEL chain (TRD §5.6). Each stage can be swapped for a passthrough."""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda, RunnablePassthrough

from app.config import Settings, get_settings
from app.indexing.fts import FTS5Retriever
from app.indexing.vector_store import get_store
from app.prompts import load_prompt
from app.query.answer import NOT_FOUND, NOT_FOUND_REPLY, format_excerpts, parse_answer
from app.query.citations import pick_citations
from app.query.rerank import rerank
from app.query.rewrite import identity_rewrite
from app.query.rrf import rrf_merge
from app.query.trace import build_trace


def build_ask_chain(
    *,
    session_factory,
    group_id: int,
    embeddings,
    reranker,
    answer_llm,
    rewriter: Runnable | None = None,
    chroma_dir: str | None = None,
    settings: Settings | None = None,
) -> Runnable:
    s = settings or get_settings()
    vector = get_store(group_id, embeddings, chroma_dir).as_retriever(
        search_kwargs={"k": s.vector_top_k}
    )
    fts = FTS5Retriever(session_factory=session_factory, group_id=group_id, k=s.bm25_top_k)
    answer_prompt, prompt_version = load_prompt("answer_v1")

    def queries(x) -> list[str]:
        r = x["rewrite"]
        return list(dict.fromkeys([x["question"], r.normalized, *r.expansions]))

    def retrieve_lists(x):
        # Raw per-source lists are kept (not just the merge) so the trace can report them.
        qs = queries(x)
        keyword_query = " ".join([x["question"], *x["rewrite"].keywords])
        return {
            "queries": qs,
            "vector": vector.batch(qs),
            "fts": fts.invoke(keyword_query),
            "fts_query": keyword_query,
        }

    def merge(x):
        return rrf_merge([*x["hits"]["vector"], x["hits"]["fts"]], k=s.rrf_k)

    def do_rerank(x):
        docs, best = rerank(queries(x), x["candidates"], reranker, s.rerank_top_n, s.final_top_k)
        return {"docs": docs, "best": best}

    def below_min_relevance(x) -> bool:
        top = x["top"]
        return not top["docs"] or (top["best"] is not None and top["best"] < s.min_relevance)

    def answer_inputs(x):
        today = datetime.now(ZoneInfo(s.timezone)).strftime("%d %b %Y")
        return {
            "question": x["question"],
            "today": today,
            "excerpts": format_excerpts(x["top"]["docs"]),
        }

    answer_chain = RunnablePassthrough.assign(
        raw_answer=RunnableLambda(answer_inputs) | answer_prompt | answer_llm | StrOutputParser()
    )

    def attach_citations(x):
        docs = x["top"]["docs"]
        gated = below_min_relevance(x)

        def with_trace(r: dict, cited: list) -> dict:
            trace = build_trace(
                x,
                cited_ids={d.metadata["chunk_id"] for d in cited},
                gated=gated,
                min_relevance=s.min_relevance,
                rerank_enabled=reranker is not None,
                prompt_version=prompt_version,
                tz=s.timezone,
            )
            return {**r, "trace": trace}

        result = {
            "found": False,
            "answer": NOT_FOUND_REPLY,
            "sources": [],
            "interpreted_range": None,
            "chunk_ids": [d.metadata["chunk_id"] for d in docs],
            "best_score": x["top"]["best"],
            "prompt_version": prompt_version,
        }
        answer, nums, not_found = parse_answer(x["raw_answer"])
        if not_found:
            return with_trace(result, [])
        nums = [n for n in dict.fromkeys(nums) if 1 <= n <= len(docs)] or [1]
        # Each source remembers which excerpt it came from, so inline [n] markers resolve to it
        cited = [
            Document(
                page_content=docs[n - 1].page_content,
                metadata={**docs[n - 1].metadata, "excerpt": n},
            )
            for n in nums
        ]
        sources = pick_citations(answer, cited, session_factory, embeddings)
        return with_trace({**result, "found": True, "answer": answer, "sources": sources}, cited)

    return (
        RunnablePassthrough.assign(rewrite=rewriter or RunnableLambda(identity_rewrite))
        | RunnablePassthrough.assign(hits=RunnableLambda(retrieve_lists))
        | RunnablePassthrough.assign(candidates=RunnableLambda(merge))
        | RunnablePassthrough.assign(top=RunnableLambda(do_rerank))
        | RunnableBranch(
            (below_min_relevance, RunnablePassthrough.assign(raw_answer=lambda _: NOT_FOUND)),
            answer_chain,
        )
        | RunnableLambda(attach_citations)
    )
