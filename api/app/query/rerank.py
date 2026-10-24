from langchain_core.documents import Document


def rerank(
    queries: list[str], docs: list[Document], reranker, top_n: int, final_k: int
) -> tuple[list[Document], float | None]:
    """Cross-encoder rerank. Each candidate keeps its best score over the query variants, since
    the reranker misses Hinglish paraphrases ("payment" vs "paisa") that rewrite expansions
    cover. Returns (top docs, best score); best is None when the reranker is disabled."""
    candidates = docs[:top_n]
    if reranker is None or not candidates:
        return candidates[:final_k], None
    pairs = [(q, d.page_content) for d in candidates for q in queries]
    flat = [float(s) for s in reranker.score(pairs)]
    n = len(queries)
    best_per_doc = [max(flat[i * n : (i + 1) * n]) for i in range(len(candidates))]
    ranked = sorted(zip(best_per_doc, candidates, strict=True), key=lambda x: x[0], reverse=True)
    top = [
        Document(page_content=d.page_content, metadata={**d.metadata, "rerank_score": s})
        for s, d in ranked[:final_k]
    ]
    return top, ranked[0][0]
