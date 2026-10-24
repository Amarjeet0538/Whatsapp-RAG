"""Time-gap segmentation plus sliding window (TRD §5.4)."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ChunkParams:
    gap_minutes: int
    window_size: int
    window_overlap: int
    max_chunk_tokens: int
    min_chunk_chars: int

    @classmethod
    def from_settings(cls, s) -> "ChunkParams":
        return cls(
            s.chunk_gap_minutes,
            s.window_size,
            s.window_overlap,
            s.max_chunk_tokens,
            s.min_chunk_chars,
        )


@dataclass
class MessageIn:
    id: int
    ts: datetime
    sender: str | None
    text_raw: str
    text_clean: str
    is_system: bool = False


@dataclass
class ChunkDraft:
    messages: list[MessageIn]

    @property
    def message_ids(self) -> list[int]:
        return [m.id for m in self.messages]

    @property
    def start_ts(self) -> datetime:
        return self.messages[0].ts

    @property
    def end_ts(self) -> datetime:
        return self.messages[-1].ts

    @property
    def participants(self) -> list[str]:
        return list(dict.fromkeys(m.sender for m in self.messages if m.sender))

    @property
    def text(self) -> str:
        lines, day = [], None
        for m in self.messages:
            if m.ts.date() != day:
                day = m.ts.date()
                lines.append(m.ts.strftime("%d %b %Y"))
            lines.append(f"[{m.ts:%H:%M}] {m.sender}: {m.text_raw}")
        return "\n".join(lines)

    @property
    def text_clean(self) -> str:
        return " ".join(m.text_clean for m in self.messages)


def approx_tokens(text: str) -> int:
    # ~4 chars per token; good enough for a size cap without loading a tokenizer
    return len(text) // 4 + 1


def _conversations(msgs: list[MessageIn], gap: timedelta) -> list[list[MessageIn]]:
    convs: list[list[MessageIn]] = []
    for m in msgs:
        if convs and m.ts - convs[-1][-1].ts <= gap:
            convs[-1].append(m)
        else:
            convs.append([m])
    return convs


def _windows(conv: list[MessageIn], size: int, overlap: int) -> list[list[MessageIn]]:
    step = max(1, size - overlap)
    out, start = [], 0
    while True:
        out.append(conv[start : start + size])
        if start + size >= len(conv):
            return out
        start += step


def _cap(window: list[MessageIn], max_tokens: int) -> list[ChunkDraft]:
    draft = ChunkDraft(window)
    if len(window) == 1 or approx_tokens(draft.text) <= max_tokens:
        return [draft]
    mid = len(window) // 2
    return _cap(window[:mid], max_tokens) + _cap(window[mid:], max_tokens)


def _merge_short(chunks: list[ChunkDraft], min_chars: int) -> list[ChunkDraft]:
    out: list[ChunkDraft] = []
    for c in chunks:
        if out and len(c.text) < min_chars:
            seen = set(out[-1].message_ids)
            out[-1] = ChunkDraft(out[-1].messages + [m for m in c.messages if m.id not in seen])
        else:
            out.append(c)
    if len(out) > 1 and len(out[0].text) < min_chars:
        first = out.pop(0)
        seen = set(out[0].message_ids)
        out[0] = ChunkDraft([m for m in first.messages if m.id not in seen] + out[0].messages)
    return out


def build_chunks(messages: list[MessageIn], p: ChunkParams) -> list[ChunkDraft]:
    msgs = sorted((m for m in messages if not m.is_system), key=lambda m: m.ts)
    chunks = []
    for conv in _conversations(msgs, timedelta(minutes=p.gap_minutes)):
        for w in _windows(conv, p.window_size, p.window_overlap):
            chunks.extend(_cap(w, p.max_chunk_tokens))
    return _merge_short(chunks, p.min_chunk_chars)
