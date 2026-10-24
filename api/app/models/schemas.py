"""Pydantic schemas: API bodies and structured-output models."""

from pydantic import BaseModel, Field


class Rewrite(BaseModel):
    normalized: str = Field(description="Question with standard spelling, same language")
    expansions: list[str] = Field(default_factory=list, description="2-3 alternative phrasings")
    keywords: list[str] = Field(default_factory=list, description="3-8 search keywords")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    user_id: str = Field(
        min_length=1, description="Sender ref: WhatsApp id, or display name for imported chats"
    )


class Source(BaseModel):
    sender: str | None
    ts: str
    snippet: str


class AskResponse(BaseModel):
    answer: str
    found: bool
    interpreted_range: dict | None = None
    sources: list[Source]
    latency_ms: int


class ImportResponse(BaseModel):
    group_id: int
    new_messages: int
    chunks: int
