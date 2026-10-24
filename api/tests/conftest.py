from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.config import ROOT
from app.db import init_db, make_engine, session_factory

SAMPLE = ROOT / "data" / "samples" / "college_project_android.txt"


@pytest.fixture
def engine(tmp_path: Path):
    eng = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(eng)
    return eng


@pytest.fixture
def Session(engine):
    return session_factory(engine)


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=32)


@pytest.fixture
def chroma_dir(tmp_path: Path) -> str:
    return str(tmp_path / "chroma")


@pytest.fixture
def sample_chat() -> str:
    return SAMPLE.read_text(encoding="utf-8")


class BagOfWordsEmbeddings:
    """Deterministic, overlap-sensitive fake: cosine similarity tracks shared cleaned words."""

    size = 512

    def _vec(self, text: str) -> list[float]:
        import math
        import re
        import zlib

        from app.ingestion.cleaner import clean_text

        v = [0.0] * self.size
        for w in re.findall(r"\w+", clean_text(text)):
            v[zlib.crc32(w.encode()) % self.size] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class OverlapReranker:
    """Fake cross-encoder: -11 (irrelevant) plus 3 per shared word, capped at 0."""

    def score(self, pairs):
        import re

        out = []
        for q, p in pairs:
            shared = set(re.findall(r"\w+", q.lower())) & set(re.findall(r"\w+", p.lower()))
            out.append(min(0.0, -11.0 + 3 * len(shared)))
        return out


@pytest.fixture
def bow_embeddings():
    return BagOfWordsEmbeddings()
