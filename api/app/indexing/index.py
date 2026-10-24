"""(Re)build a group's chunks and both derived indexes from `messages` (TRD §5.4, §5.5, §9)."""

import json

from langchain_core.embeddings import Embeddings
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.indexing.chunker import ChunkParams, MessageIn, build_chunks
from app.indexing.documents import chunk_to_document
from app.indexing.vector_store import drop_store, get_store
from app.models.db import Chunk, Message, User


def index_group(
    session: Session, group_id: int, embeddings: Embeddings, chroma_dir: str | None = None
) -> int:
    rows = session.execute(
        select(Message, User.display_name)
        .outerjoin(User, Message.sender_id == User.id)
        .where(Message.group_id == group_id)
        .order_by(Message.ts, Message.id)
    ).all()
    drafts = build_chunks(
        [
            MessageIn(m.id, m.ts, name, m.text_raw, m.text_clean or "", m.is_system)
            for m, name in rows
        ],
        ChunkParams.from_settings(get_settings()),
    )

    session.execute(text("DELETE FROM chunks_fts WHERE group_id = :g"), {"g": group_id})
    session.execute(delete(Chunk).where(Chunk.group_id == group_id))
    chunks = [
        Chunk(
            group_id=group_id,
            start_ts=d.start_ts,
            end_ts=d.end_ts,
            participants=", ".join(d.participants),
            message_ids=json.dumps(d.message_ids),
            text=d.text,
        )
        for d in drafts
    ]
    session.add_all(chunks)
    session.flush()
    session.execute(
        text("INSERT INTO chunks_fts(rowid, text_clean, group_id) VALUES (:id, :t, :g)"),
        [
            {"id": c.id, "t": d.text_clean, "g": group_id}
            for c, d in zip(chunks, drafts, strict=True)
        ],
    )

    drop_store(group_id, chroma_dir)
    if chunks:
        docs = [chunk_to_document(c) for c in chunks]
        get_store(group_id, embeddings, chroma_dir).add_documents(docs, ids=[d.id for d in docs])
    session.commit()
    return len(chunks)
