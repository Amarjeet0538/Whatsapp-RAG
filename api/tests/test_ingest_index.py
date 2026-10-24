from sqlalchemy import func, select, text

from app.indexing.fts import FTS5Retriever
from app.indexing.index import index_group
from app.indexing.vector_store import get_store
from app.ingestion.service import import_chat
from app.models.db import Chunk, Membership, Message, User


def test_import_stores_messages_users_and_memberships(Session, sample_chat):
    with Session() as s:
        res = import_chat(s, "grp-1", sample_chat, name="Final Year Project")
        assert res.new_messages == 49
        assert s.scalar(select(func.count()).select_from(Message).where(Message.is_system)) == 5
        assert sorted(s.scalars(select(User.display_name))) == [
            "Amit Client",
            "Priya",
            "Rahul",
            "Riya",
        ]
        assert s.scalar(select(func.count()).select_from(Membership)) == 4


def test_reimport_of_same_export_adds_nothing(Session, sample_chat):
    with Session() as s:
        import_chat(s, "grp-1", sample_chat)
        assert import_chat(s, "grp-1", sample_chat).new_messages == 0


def test_phone_like_sender_ids_are_hashed_not_stored(Session):
    with Session() as s:
        import_chat(s, "grp-1", "12/03/2026, 14:05 - +91 98765 43210: hi\n")
        stored = s.scalar(select(User.wa_id_hash))
    assert "98765" not in stored


def _index(Session, sample_chat, fake_embeddings, chroma_dir, wa="grp-1"):
    with Session() as s:
        gid = import_chat(s, wa, sample_chat).group_id
        n = index_group(s, gid, fake_embeddings, chroma_dir)
    return gid, n


def test_index_fills_db_fts_and_vector_store(Session, sample_chat, fake_embeddings, chroma_dir):
    gid, n = _index(Session, sample_chat, fake_embeddings, chroma_dir)
    with Session() as s:
        assert n > 1
        assert s.scalar(select(func.count()).select_from(Chunk)) == n
        assert s.execute(text("SELECT count(*) FROM chunks_fts")).scalar() == n
    assert get_store(gid, fake_embeddings, chroma_dir)._collection.count() == n


def test_reindex_is_idempotent(Session, sample_chat, fake_embeddings, chroma_dir):
    gid, n = _index(Session, sample_chat, fake_embeddings, chroma_dir)
    with Session() as s:
        assert index_group(s, gid, fake_embeddings, chroma_dir) == n
        assert s.scalar(select(func.count()).select_from(Chunk)) == n
    assert get_store(gid, fake_embeddings, chroma_dir)._collection.count() == n


def test_fts_retriever_matches_keyword_within_group_only(
    Session, sample_chat, fake_embeddings, chroma_dir
):
    gid, _ = _index(Session, sample_chat, fake_embeddings, chroma_dir)
    other, _ = _index(
        Session, "12/03/2026, 14:05 - Zed: koi aur baat\n", fake_embeddings, chroma_dir, "grp-2"
    )
    docs = FTS5Retriever(session_factory=Session, group_id=gid, k=5).invoke("installment")
    assert docs and "installment" in docs[0].page_content
    assert docs[0].metadata["group_id"] == gid and "start_ts" in docs[0].metadata
    assert FTS5Retriever(session_factory=Session, group_id=other, k=5).invoke("installment") == []
