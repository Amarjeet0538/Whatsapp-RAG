"""Pick the most relevant message(s) inside each cited chunk (TRD §5.6 post-processing)."""

import json
from zoneinfo import ZoneInfo

import numpy as np
from langchain_core.documents import Document
from sqlalchemy import select

from app.config import get_settings
from app.models.db import Message, User

SNIPPET_CHARS = 200
# The answer prompt asks the LLM to say who said it and when. A message whose HH:MM the answer
# quotes is almost certainly the source; similarity alone ties a question with its reply.
TIME_MENTION_BOOST = 0.5


def pick_citations(
    answer: str, docs: list[Document], session_factory, embeddings, per_doc: int = 1
) -> list[dict]:
    ids = [i for d in docs for i in json.loads(d.metadata["message_ids"])]
    with session_factory() as s:
        rows = s.execute(
            select(Message, User.display_name)
            .outerjoin(User, Message.sender_id == User.id)
            .where(Message.id.in_(ids), Message.is_system.is_(False))
        ).all()
    by_id = {m.id: (m, name) for m, name in rows}
    tz = ZoneInfo(get_settings().timezone)
    a = np.array(embeddings.embed_query(answer))
    out, seen = [], set()
    for d in docs:
        msgs = [
            by_id[i] for i in json.loads(d.metadata["message_ids"]) if i in by_id and i not in seen
        ]
        if not msgs:
            continue
        # Same "[HH:MM] Sender: text" form as the chunk, so names and times count toward similarity
        lines = [f"[{m.ts:%H:%M}] {name}: {m.text_raw}" for m, name in msgs]
        scores = np.array(embeddings.embed_documents(lines)) @ a
        scores += [TIME_MENTION_BOOST if f"{m.ts:%H:%M}" in answer else 0.0 for m, _ in msgs]
        for j in np.argsort(-scores)[:per_doc]:
            m, name = msgs[j]
            seen.add(m.id)
            out.append(
                {
                    "sender": name,
                    "ts": m.ts.replace(tzinfo=tz).isoformat(),
                    "snippet": m.text_raw[:SNIPPET_CHARS],
                }
            )
    return out
