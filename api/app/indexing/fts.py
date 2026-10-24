"""BM25 keyword retrieval over SQLite FTS5, as a LangChain retriever (TRD §5.5)."""

import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from sqlalchemy import select, text

from app.indexing.documents import chunk_to_document
from app.ingestion.cleaner import clean_text
from app.models.db import Chunk

_TOKEN = re.compile(r"\w+")


def fts_query(query: str) -> str:
    """OR of quoted tokens from the cleaned query; quoting neutralizes FTS5 syntax in user text."""
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(_TOKEN.findall(clean_text(query))))


class FTS5Retriever(BaseRetriever):
    session_factory: Any
    group_id: int
    k: int = 20

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        match = fts_query(query)
        if not match:
            return []
        with self.session_factory() as s:
            ids = (
                s.execute(
                    text(
                        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH :q AND group_id = :g "
                        "ORDER BY bm25(chunks_fts) LIMIT :k"
                    ),
                    {"q": match, "g": self.group_id, "k": self.k},
                )
                .scalars()
                .all()
            )
            rows = {c.id: c for c in s.scalars(select(Chunk).where(Chunk.id.in_(ids)))}
        return [chunk_to_document(rows[i]) for i in ids if i in rows]
