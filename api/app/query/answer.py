"""Excerpt formatting and answer parsing for the grounded answer prompt (TRD §5.6)."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.documents import Document

from app.config import get_settings

NOT_FOUND = "NOT_FOUND"
NOT_FOUND_REPLY = "I couldn't find this in the chat. (Chat mein iske baare mein kuch nahi mila.)"
_SOURCES = re.compile(r"\n?\s*SOURCES:\s*\[([\d,\s]*)\]\s*$", re.I)


def format_excerpts(docs: list[Document]) -> str:
    """Chat text is untrusted: each excerpt sits in its own delimited block."""
    tz = ZoneInfo(get_settings().timezone)
    blocks = []
    for i, d in enumerate(docs, start=1):
        date = datetime.fromtimestamp(d.metadata["start_ts"], tz).strftime("%d %b %Y")
        participants = d.metadata.get("participants", "")
        blocks.append(
            f'<excerpt id="{i}" date="{date}" participants="{participants}">\n'
            f"{d.page_content}\n</excerpt>"
        )
    return "\n\n".join(blocks)


def parse_answer(raw: str) -> tuple[str, list[int], bool]:
    """Returns (answer text, 1-based excerpt numbers, not_found)."""
    text = raw.strip()
    m = _SOURCES.search(text)
    sources = [int(x) for x in m.group(1).replace(" ", "").split(",") if x] if m else []
    answer = text[: m.start()].strip() if m else text
    return answer, sources, answer.upper().startswith(NOT_FOUND)
