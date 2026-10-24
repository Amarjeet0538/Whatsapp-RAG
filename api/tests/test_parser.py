from datetime import datetime

import pytest

from app.ingestion.parser import ParseError, parse_export


def test_android_24h():
    msgs = parse_export(
        "12/03/2026, 14:05 - Rahul: kal tak report bhej dunga\n"
        "13/03/2026, 09:30 - Riya Sharma: ok\n"
    )
    assert [(m.ts, m.sender, m.text, m.is_system) for m in msgs] == [
        (datetime(2026, 3, 12, 14, 5), "Rahul", "kal tak report bhej dunga", False),
        (datetime(2026, 3, 13, 9, 30), "Riya Sharma", "ok", False),
    ]


def test_android_12h_with_narrow_nbsp():
    msgs = parse_export("12/03/26, 2:05 pm - Rahul: hi\n12/03/26, 12:10 am - Amit: so ja\n")
    assert [m.ts for m in msgs] == [datetime(2026, 3, 12, 14, 5), datetime(2026, 3, 12, 0, 10)]


def test_ios_bracketed_with_seconds_and_lrm():
    msgs = parse_export(
        "[12/03/26, 2:05:13 PM] Rahul: payment 20 tarikh tak\n"
        "‎[12/03/26, 2:06:00 PM] Amit: ‎image omitted\n"
    )
    assert (msgs[0].ts, msgs[0].sender, msgs[0].text) == (
        datetime(2026, 3, 12, 14, 5, 13),
        "Rahul",
        "payment 20 tarikh tak",
    )
    assert msgs[1].is_system is True


def test_multiline_message_joined():
    msgs = parse_export("12/03/2026, 14:05 - Rahul: line one\nline two\n\nline four\n")
    assert len(msgs) == 1
    assert msgs[0].text == "line one\nline two\n\nline four"


def test_system_lines_flagged():
    msgs = parse_export(
        "12/03/2026, 14:00 - Messages and calls are end-to-end encrypted. Tap to learn more.\n"
        "12/03/2026, 14:01 - Rahul joined using this group's invite link\n"
        "12/03/2026, 14:02 - Rahul: <Media omitted>\n"
        "12/03/2026, 14:03 - Riya: This message was deleted\n"
        "12/03/2026, 14:04 - Riya: real text\n"
    )
    assert [m.is_system for m in msgs] == [True, True, True, True, False]
    assert msgs[0].sender is None


def test_month_first_detected_from_values_above_12():
    msgs = parse_export("03/12/2026, 10:00 - A: x\n03/25/2026, 10:00 - B: y\n")
    assert [m.ts.date() for m in msgs] == [
        datetime(2026, 3, 12).date(),
        datetime(2026, 3, 25).date(),
    ]


def test_day_first_is_default_when_ambiguous():
    assert parse_export("03/04/2026, 10:00 - A: x\n")[0].ts == datetime(2026, 4, 3, 10, 0)


def test_bom_is_ignored():
    assert parse_export("﻿12/03/2026, 14:05 - Rahul: hi\n")[0].sender == "Rahul"


def test_unparseable_file_raises_with_hint():
    with pytest.raises(ParseError, match="Android"):
        parse_export("hello\nthis is not a chat export\n")
