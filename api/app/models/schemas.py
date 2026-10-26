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
    message_id: int
    excerpt: int  # the [n] the answer used for this source
    sender: str | None
    ts: str
    snippet: str


class TraceQuery(BaseModel):
    text: str
    vector_hits: int


class TraceRetrieval(BaseModel):
    queries: list[TraceQuery]
    fts_query: str
    fts_hits: int
    merged: int


class TraceChunk(BaseModel):
    chunk_id: int
    start_ts: str
    end_ts: str
    participants: str
    score: float | None  # raw cross-encoder logit, not a probability
    preview: str
    cited: bool


class Trace(BaseModel):
    rewrite: Rewrite
    retrieval: TraceRetrieval
    reranked: list[TraceChunk]
    best_score: float | None
    min_relevance: float
    gated: bool
    rerank_enabled: bool
    prompt_version: str
    latency_ms: int = 0


class AskResponse(BaseModel):
    answer: str
    found: bool
    interpreted_range: dict | None = None
    sources: list[Source]
    latency_ms: int
    trace: Trace


class ImportResponse(BaseModel):
    group_id: int
    new_messages: int
    chunks: int


class GroupSummary(BaseModel):
    wa_group_id: str
    name: str | None
    message_count: int
    member_count: int
    last_message_ts: str | None


class MemberSummary(BaseModel):
    display_name: str
    message_count: int


class ContextMessage(BaseModel):
    id: int
    sender: str | None
    ts: str
    text: str
    is_target: bool


class ContextResponse(BaseModel):
    target_id: int
    messages: list[ContextMessage]
