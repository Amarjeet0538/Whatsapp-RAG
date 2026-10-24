"""Builds `text_clean` for indexing (TRD §5.3). Apply the same function to queries."""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import emoji
import yaml

_URL = re.compile(r"https?://\S+|www\.\S+")
# 10+ digits with optional +code, spaces or dashes; short numbers (amounts, dates) survive
_PHONE = re.compile(r"\+?\d[\d \-]{8,}\d")
_REPEAT = re.compile(r"([^\W\d_])\1{2,}")  # letters only: "5000" must survive
_SPACES = re.compile(r"[ \t]+")
_WORD = re.compile(r"[a-z]+")


@lru_cache
def _variant_map() -> dict[str, str]:
    table = yaml.safe_load((Path(__file__).parent / "hinglish_norm.yaml").read_text())
    return {v: canon for canon, variants in table.items() for v in variants or []}


def _emoji_to_words(text: str) -> str:
    return emoji.replace_emoji(
        text, replace=lambda e, data: " " + data["en"].strip(":").replace("_", " ") + " "
    )


def clean_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = _URL.sub("<url>", t)
    t = _PHONE.sub("<phone>", t)
    t = _emoji_to_words(t).lower()
    t = _REPEAT.sub(r"\1\1", t)
    variants = _variant_map()
    t = _WORD.sub(lambda m: variants.get(m.group(), m.group()), t)
    return _SPACES.sub(" ", t).strip()
