"""One Chroma collection per group, `grp_<group_id>` (TRD §5.5, §6.2)."""

from functools import lru_cache
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from app.config import ROOT, get_settings


@lru_cache
def _client(path: str) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=path, settings=chromadb.Settings(anonymized_telemetry=False)
    )


def _path(chroma_dir: str | None) -> str:
    p = Path(chroma_dir or get_settings().chroma_dir)
    return str(p if p.is_absolute() else ROOT / p)


def collection_name(group_id: int) -> str:
    return f"grp_{group_id}"


def get_store(group_id: int, embeddings: Embeddings, chroma_dir: str | None = None) -> Chroma:
    return Chroma(
        client=_client(_path(chroma_dir)),
        collection_name=collection_name(group_id),
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine"},
    )


def drop_store(group_id: int, chroma_dir: str | None = None) -> None:
    client = _client(_path(chroma_dir))
    if collection_name(group_id) in [c.name for c in client.list_collections()]:
        client.delete_collection(collection_name(group_id))
