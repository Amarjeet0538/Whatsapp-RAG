"""Import a chat export into the relational DB (TRD §5.2). Indexing is separate (app.indexing)."""

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.cleaner import clean_text
from app.ingestion.parser import parse_export
from app.models.db import Group, Membership, Message, User

_PHONE_LIKE = re.compile(r"^\+?[\d\s\-()]{8,}$")


@dataclass
class ImportResult:
    group_id: int
    new_messages: int


def hash_id(ref: str) -> str:
    """Salted hash for phone numbers / sender ids (TRD §10)."""
    return hashlib.sha256(f"{get_settings().id_hash_salt}:{ref}".encode()).hexdigest()


def dedup_key(group_id: int, ts, sender: str | None, text_raw: str) -> str:
    return hashlib.sha1(
        f"{group_id}|{ts.isoformat()}|{sender or ''}|{text_raw}".encode()
    ).hexdigest()


def _display_name(sender: str) -> str:
    if _PHONE_LIKE.match(sender):
        digits = re.sub(r"\D", "", sender)
        return f"+•••{digits[-4:]}"
    return sender


def get_or_create_group(session: Session, wa_group_id: str, name: str | None = None) -> Group:
    group = session.scalar(select(Group).where(Group.wa_group_id == wa_group_id))
    if group is None:
        group = Group(wa_group_id=wa_group_id, name=name)
        session.add(group)
        session.flush()
    return group


def get_or_create_member(session: Session, group: Group, ref: str, display: str) -> User:
    h = hash_id(ref)
    user = session.scalar(select(User).where(User.wa_id_hash == h))
    if user is None:
        user = User(wa_id_hash=h, display_name=display)
        session.add(user)
        session.flush()
    if session.get(Membership, (user.id, group.id)) is None:
        session.add(Membership(user_id=user.id, group_id=group.id))
    return user


def import_chat(
    session: Session, wa_group_id: str, content: str, name: str | None = None
) -> ImportResult:
    parsed = parse_export(content)
    group = get_or_create_group(session, wa_group_id, name)
    existing = set(session.scalars(select(Message.dedup_key).where(Message.group_id == group.id)))
    users: dict[str, User] = {}
    new = 0
    for pm in parsed:
        key = dedup_key(group.id, pm.ts, pm.sender, pm.text)
        if key in existing:
            continue
        existing.add(key)
        sender_id = None
        if pm.sender:
            if pm.sender not in users:
                # Exports carry contact names, not phone numbers; live messages use the wa id.
                users[pm.sender] = get_or_create_member(
                    session, group, f"name:{pm.sender}", _display_name(pm.sender)
                )
            sender_id = users[pm.sender].id
        session.add(
            Message(
                group_id=group.id,
                sender_id=sender_id,
                ts=pm.ts,
                text_raw=pm.text,
                text_clean=None if pm.is_system else clean_text(pm.text),
                is_system=pm.is_system,
                source="import",
                dedup_key=key,
            )
        )
        new += 1
        if new % 1000 == 0:
            session.flush()
    session.commit()
    return ImportResult(group.id, new)
