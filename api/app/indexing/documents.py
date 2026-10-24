from zoneinfo import ZoneInfo

from langchain_core.documents import Document

from app.config import get_settings
from app.models.db import Chunk


def epoch(dt, tz: ZoneInfo | None = None) -> int:
    return int(dt.replace(tzinfo=tz or ZoneInfo(get_settings().timezone)).timestamp())


def chunk_to_document(c: Chunk) -> Document:
    """Chroma metadata must be scalar: epoch ints and joined strings (TRD §6.2)."""
    return Document(
        id=f"chunk_{c.id}",
        page_content=c.text,
        metadata={
            "chunk_id": c.id,
            "group_id": c.group_id,
            "start_ts": epoch(c.start_ts),
            "end_ts": epoch(c.end_ts),
            "participants": c.participants,
            "message_ids": c.message_ids,
        },
    )
