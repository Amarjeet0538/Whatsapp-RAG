import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda
from tests.conftest import OverlapReranker

from app.indexing.index import index_group
from app.ingestion.service import import_chat
from app.models.schemas import Rewrite
from app.query.answer import NOT_FOUND_REPLY
from app.query.chain import build_ask_chain

REWRITE = Rewrite(
    normalized="payment kab aayega",
    expansions=["paisa kab aayega", "installment kab milegi"],
    keywords=["payment", "paisa", "installment"],
)


class AlwaysIrrelevant:
    def score(self, pairs):
        return [-11.0] * len(pairs)


@pytest.fixture
def group_id(Session, sample_chat, bow_embeddings, chroma_dir):
    with Session() as s:
        gid = import_chat(s, "grp-1", sample_chat).group_id
        index_group(s, gid, bow_embeddings, chroma_dir)
    return gid


def ask(Session, group_id, emb, chroma_dir, llm, reranker):
    chain = build_ask_chain(
        session_factory=Session,
        group_id=group_id,
        embeddings=emb,
        reranker=reranker,
        answer_llm=llm,
        rewriter=RunnableLambda(lambda x: REWRITE),
        chroma_dir=chroma_dir,
    )
    return chain.invoke({"question": "client ne payment kab bola?"})


def test_sources_carry_the_excerpt_number_the_llm_cited(
    Session, group_id, bow_embeddings, chroma_dir
):
    # The UI maps an inline [n] to the source whose excerpt is n, not to sources[n-1].
    llm = FakeListChatModel(responses=["Paisa 20 tarikh tak aayega [3].\nSOURCES: [3, 1]"])
    out = ask(Session, group_id, bow_embeddings, chroma_dir, llm, OverlapReranker())
    assert [s["excerpt"] for s in out["sources"]] == [3, 1]


def test_grounded_answer_cites_the_source_message(Session, group_id, bow_embeddings, chroma_dir):
    llm = FakeListChatModel(
        responses=["Pehli installment ka paisa 20 tarikh tak aayega.\nSOURCES: [1]"]
    )
    out = ask(Session, group_id, bow_embeddings, chroma_dir, llm, OverlapReranker())
    assert out["found"] is True
    assert out["answer"] == "Pehli installment ka paisa 20 tarikh tak aayega."
    assert out["sources"][0]["sender"] == "Amit Client"
    assert "20 tarikh" in out["sources"][0]["snippet"]
    assert out["sources"][0]["ts"].startswith("2026-10-02T11:14:00+05:30")


def test_low_relevance_returns_not_found_without_calling_llm(
    Session, group_id, bow_embeddings, chroma_dir
):
    llm = FakeListChatModel(responses=[])  # any call raises
    out = ask(Session, group_id, bow_embeddings, chroma_dir, llm, AlwaysIrrelevant())
    assert out == {**out, "found": False, "answer": NOT_FOUND_REPLY, "sources": []}


def test_llm_not_found_reply_maps_to_not_found(Session, group_id, bow_embeddings, chroma_dir):
    out = ask(
        Session,
        group_id,
        bow_embeddings,
        chroma_dir,
        FakeListChatModel(responses=["NOT_FOUND"]),
        OverlapReranker(),
    )
    assert (out["found"], out["answer"], out["sources"]) == (False, NOT_FOUND_REPLY, [])


def test_citation_prefers_message_whose_time_the_answer_mentions(Session, group_id, bow_embeddings):
    from app.indexing.fts import FTS5Retriever
    from app.query.citations import pick_citations

    doc = FTS5Retriever(session_factory=Session, group_id=group_id, k=1).invoke("bhejoge")[0]
    answer = (
        "Rahul promised to send the database report by the next day (kal tak), "
        "on 05 Oct 2026 at 20:15."
    )
    [src] = pick_citations(answer, [doc], Session, bow_embeddings)
    assert (src["sender"], src["ts"][11:16]) == ("Rahul", "20:15")
