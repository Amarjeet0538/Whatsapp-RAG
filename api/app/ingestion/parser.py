"""WhatsApp .txt export parser for Android and iOS formats (TRD §5.2)."""

import re
from dataclasses import dataclass
from datetime import datetime

SUPPORTED_FORMATS = (
    "Android: '12/03/2026, 14:05 - Rahul: message' (12h or 24h)\n"
    "iOS: '[12/03/26, 2:05:13 PM] Rahul: message'"
)

_TIME = r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)(?:[\s  ]*(?P<ampm>[AaPp]\.?[Mm]\.?))?"
_DATE = r"(?P<d1>\d{1,2})[/.-](?P<d2>\d{1,2})[/.-](?P<year>\d{2,4})"
PATTERNS = {
    "android": re.compile(rf"^{_DATE},? {_TIME} - (?P<body>.*)$"),
    "ios": re.compile(rf"^\[{_DATE},? {_TIME}\] (?P<body>.*)$"),
}

# A sender name is followed by ": ". Lines without it (joins, encryption notice) are system lines.
_SENDER = re.compile(r"^(?P<sender>[^:]{1,60}?): (?P<text>.*)$", re.S)
_SYSTEM_TEXT = re.compile(
    r"^(<media omitted>|this message was deleted|you deleted this message|"
    r"(image|video|audio|sticker|gif|document) omitted|null|<this message was edited>)$",
    re.I,
)
_INVISIBLE = str.maketrans("", "", "‎‏﻿")


class ParseError(ValueError):
    pass


@dataclass
class ParsedMessage:
    ts: datetime
    sender: str | None
    text: str
    is_system: bool


def _detect_pattern(lines: list[str]) -> re.Pattern:
    counts = {name: sum(1 for ln in lines if p.match(ln)) for name, p in PATTERNS.items()}
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        raise ParseError(
            f"No line matched a known WhatsApp export format. Supported:\n{SUPPORTED_FORMATS}"
        )
    return PATTERNS[best]


def _day_first(matches: list[re.Match]) -> bool:
    if any(int(m["d1"]) > 12 for m in matches):
        return True
    if any(int(m["d2"]) > 12 for m in matches):
        return False
    return True  # Indian exports are DD/MM


def _to_datetime(m: re.Match, day_first: bool) -> datetime:
    d1, d2, year = int(m["d1"]), int(m["d2"]), int(m["year"])
    day, month = (d1, d2) if day_first else (d2, d1)
    if year < 100:
        year += 2000
    parts = [int(x) for x in m["time"].split(":")]
    hour, minute, second = parts[0], parts[1], parts[2] if len(parts) == 3 else 0
    if m["ampm"]:
        pm = m["ampm"][0].lower() == "p"
        hour = hour % 12 + (12 if pm else 0)
    return datetime(year, month, day, hour, minute, second)


def parse_export(content: str) -> list[ParsedMessage]:
    lines = [ln.translate(_INVISIBLE).rstrip("\r") for ln in content.split("\n")]
    pattern = _detect_pattern(lines)

    # Group each timestamped line with its continuation lines.
    entries: list[tuple[re.Match, list[str]]] = []
    for ln in lines:
        m = pattern.match(ln)
        if m:
            entries.append((m, [m["body"]]))
        elif entries:
            entries[-1][1].append(ln)

    day_first = _day_first([m for m, _ in entries])
    messages = []
    for m, body_lines in entries:
        body = "\n".join(body_lines).rstrip("\n")
        sm = _SENDER.match(body)
        if sm:
            sender, text = sm["sender"].strip(), sm["text"].strip()
            is_system = bool(_SYSTEM_TEXT.match(text))
        else:
            sender, text, is_system = None, body.strip(), True
        messages.append(ParsedMessage(_to_datetime(m, day_first), sender, text, is_system))
    return messages
