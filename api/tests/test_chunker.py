from datetime import datetime, timedelta

from app.indexing.chunker import ChunkParams, MessageIn, build_chunks

T0 = datetime(2026, 3, 12, 10, 0)
LONG = "is message mein kaafi saare words hain taaki chunk chhota na lage"
P = ChunkParams(
    gap_minutes=30, window_size=5, window_overlap=2, max_chunk_tokens=400, min_chunk_chars=80
)


def msg(i, minutes, text=LONG, sender="Rahul", system=False):
    return MessageIn(
        id=i,
        ts=T0 + timedelta(minutes=minutes),
        sender=sender,
        text_raw=text,
        text_clean=text,
        is_system=system,
    )


def ids(chunks):
    return [c.message_ids for c in chunks]


def test_gap_over_threshold_starts_new_chunk():
    chunks = build_chunks([msg(1, 0), msg(2, 5), msg(3, 60)], P)
    assert ids(chunks) == [[1, 2], [3]]


def test_sliding_window_with_overlap():
    chunks = build_chunks([msg(i, i) for i in range(12)], P)
    assert ids(chunks) == [[0, 1, 2, 3, 4], [3, 4, 5, 6, 7], [6, 7, 8, 9, 10], [9, 10, 11]]


def test_system_messages_excluded():
    chunks = build_chunks([msg(1, 0), msg(2, 1, "<Media omitted>", system=True), msg(3, 2)], P)
    assert ids(chunks) == [[1, 3]]


def test_short_lonely_chunk_merged_into_previous():
    chunks = build_chunks([msg(1, 0), msg(2, 1), msg(3, 180, "ok")], P)
    assert ids(chunks) == [[1, 2, 3]]


def test_text_format_and_metadata():
    chunks = build_chunks(
        [msg(1, 0, "payment kab aayega?", "Amit"), msg(2, 65 + 24 * 60, LONG, "Riya")],
        ChunkParams(
            gap_minutes=10_000,
            window_size=10,
            window_overlap=3,
            max_chunk_tokens=400,
            min_chunk_chars=10,
        ),
    )
    c = chunks[0]
    assert c.text == (
        "12 Mar 2026\n[10:00] Amit: payment kab aayega?\n" f"13 Mar 2026\n[11:05] Riya: {LONG}"
    )
    assert c.participants == ["Amit", "Riya"]
    assert (c.start_ts, c.end_ts) == (T0, T0 + timedelta(minutes=65 + 24 * 60))
    assert c.text_clean == f"payment kab aayega? {LONG}"


def test_token_cap_splits_window():
    big = "word " * 120  # ~150 tokens per message at 4 chars/token
    chunks = build_chunks(
        [msg(i, i, big) for i in range(4)],
        ChunkParams(
            gap_minutes=30,
            window_size=10,
            window_overlap=3,
            max_chunk_tokens=400,
            min_chunk_chars=80,
        ),
    )
    assert ids(chunks) == [[0, 1], [2, 3]]
