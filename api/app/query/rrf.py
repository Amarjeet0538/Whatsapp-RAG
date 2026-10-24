from langchain_core.documents import Document


def rrf_merge(result_lists: list[list[Document]], k: int = 60) -> list[Document]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)), rank starting at 1 (TRD §5.6)."""
    scores: dict = {}
    docs: dict = {}
    for results in result_lists:
        for rank, d in enumerate(results, start=1):
            cid = d.metadata["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            docs.setdefault(cid, d)
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [
        Document(
            page_content=docs[c].page_content, metadata={**docs[c].metadata, "rrf_score": scores[c]}
        )
        for c in ordered
    ]
