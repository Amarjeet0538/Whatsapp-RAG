"""Shared FastAPI dependencies: auth and the (lazily loaded) models."""

import hmac
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import Header

from app.config import get_settings
from app.errors import APIError
from app.llm import get_chat_model, get_embeddings, get_reranker
from app.query.rewrite import make_rewrite_chain


@dataclass
class Models:
    embeddings: Any
    reranker: Any
    answer_llm: Any
    rewriter: Any  # None = rewrite stage off (identity)
    chroma_dir: str | None = None


@lru_cache
def get_models() -> Models:
    s = get_settings()
    llm = get_chat_model(s)
    rewriter = make_rewrite_chain(llm) if s.query_rewrite_enabled else None
    return Models(get_embeddings(s), get_reranker(s), llm, rewriter)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_api_key, get_settings().api_key):
        raise APIError(401, "UNAUTHORIZED", "Missing or invalid X-API-Key")
