"""SQLAlchemy models for TRD §6.1 (tables the MVP uses)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    wa_group_id: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    wa_id_hash: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str | None]


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    last_seen_message_id: Mapped[int | None]
    last_seen_at: Mapped[datetime | None]


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    text_raw: Mapped[str] = mapped_column(Text)
    text_clean: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_to_id: Mapped[int | None]
    source: Mapped[str] = mapped_column(String, default="import")
    dedup_key: Mapped[str] = mapped_column(String, unique=True)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    start_ts: Mapped[datetime] = mapped_column(DateTime)
    end_ts: Mapped[datetime] = mapped_column(DateTime)
    participants: Mapped[str] = mapped_column(Text)  # comma-joined display names
    message_ids: Mapped[str] = mapped_column(Text)  # JSON array
    text: Mapped[str] = mapped_column(Text)
    extracted: Mapped[int] = mapped_column(Integer, default=0)


class QueryLog(Base):
    __tablename__ = "query_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int | None]
    user_id: Mapped[int | None]
    query: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None]
    filters: Mapped[str | None] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None]
    model: Mapped[str | None]
    prompt_version: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
