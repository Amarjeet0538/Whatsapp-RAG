import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import func, literal, select, tuple_

from app.config import get_settings
from app.db import get_session_factory
from app.deps import Models, get_models, require_api_key
from app.errors import APIError
from app.indexing.index import index_group
from app.ingestion.parser import ParseError
from app.ingestion.service import hash_id, import_chat
from app.models.db import Group, Membership, Message, QueryLog, User
from app.models.schemas import (
    AskRequest,
    AskResponse,
    ContextMessage,
    ContextResponse,
    GroupSummary,
    ImportResponse,
    MemberSummary,
)
from app.query.chain import build_ask_chain

router = APIRouter(prefix="/groups", dependencies=[Depends(require_api_key)])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def member_ref(user_id: str) -> str:
    """Live senders are WhatsApp ids (contain '@'); imported senders are known by display name."""
    return user_id if "@" in user_id else f"name:{user_id}"


def local_iso(ts: datetime) -> str:
    return ts.replace(tzinfo=ZoneInfo(get_settings().timezone)).isoformat()


def get_group(s, wa_group_id: str) -> Group:
    group = s.scalar(select(Group).where(Group.wa_group_id == wa_group_id))
    if group is None:
        raise APIError(404, "GROUP_NOT_FOUND", f"No group {wa_group_id!r}")
    return group


def resolve_member(s, wa_group_id: str, user_ref: str) -> tuple[Group, User]:
    """Every endpoint that returns chat text goes through here (membership enforcement)."""
    group = get_group(s, wa_group_id)
    user = s.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.group_id == group.id, User.wa_id_hash == hash_id(member_ref(user_ref)))
    )
    if user is None:
        raise APIError(403, "NOT_A_MEMBER", "You are not a member of this group")
    return group, user


# Operator-level views: names and counts only, no chat text, so no membership check.
@router.get("", response_model=list[GroupSummary])
def list_groups(Session=Depends(get_session_factory)):
    msgs = (
        select(
            Message.group_id,
            func.count(Message.id).label("n"),
            func.max(Message.ts).label("last"),
        )
        .where(Message.is_system.is_(False))
        .group_by(Message.group_id)
        .subquery()
    )
    members = (
        select(Membership.group_id, func.count().label("n"))
        .group_by(Membership.group_id)
        .subquery()
    )
    with Session() as s:
        rows = s.execute(
            select(Group, msgs.c.n, msgs.c.last, members.c.n)
            .outerjoin(msgs, msgs.c.group_id == Group.id)
            .outerjoin(members, members.c.group_id == Group.id)
        ).all()
    out = [
        GroupSummary(
            wa_group_id=g.wa_group_id,
            name=g.name,
            message_count=n or 0,
            member_count=m or 0,
            last_message_ts=local_iso(last) if last else None,
        )
        for g, n, last, m in rows
    ]
    return sorted(out, key=lambda g: g.last_message_ts or "", reverse=True)


@router.get("/{wa_group_id}/members", response_model=list[MemberSummary])
def list_members(wa_group_id: str, Session=Depends(get_session_factory)):
    with Session() as s:
        group = get_group(s, wa_group_id)
        n = (
            select(func.count(Message.id))
            .where(
                Message.group_id == group.id,
                Message.sender_id == User.id,
                Message.is_system.is_(False),
            )
            .scalar_subquery()
        )
        rows = s.execute(
            select(User.display_name, n.label("n"))
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.group_id == group.id, User.display_name.is_not(None))
            .order_by(n.desc(), User.display_name)
        ).all()
    return [MemberSummary(display_name=name, message_count=c) for name, c in rows]


@router.get("/{wa_group_id}/messages/{message_id}/context", response_model=ContextResponse)
def get_context(
    wa_group_id: str,
    message_id: int,
    user_id: str,
    window: int = Query(5, ge=1, le=20),
    Session=Depends(get_session_factory),
):
    with Session() as s:
        group, _ = resolve_member(s, wa_group_id, user_id)
        target = s.get(Message, message_id)
        if target is None or target.group_id != group.id or target.is_system:
            raise APIError(404, "MESSAGE_NOT_FOUND", f"No message {message_id} in this group")
        base = (
            select(Message, User.display_name)
            .outerjoin(User, Message.sender_id == User.id)
            .where(Message.group_id == group.id, Message.is_system.is_(False))
        )
        key = tuple_(Message.ts, Message.id)
        here = tuple_(literal(target.ts), literal(target.id))
        before = s.execute(
            base.where(key < here).order_by(Message.ts.desc(), Message.id.desc()).limit(window)
        ).all()
        after = s.execute(
            base.where(key >= here).order_by(Message.ts, Message.id).limit(window + 1)
        ).all()
    return ContextResponse(
        target_id=target.id,
        messages=[
            ContextMessage(
                id=m.id,
                sender=name,
                ts=local_iso(m.ts),
                text=m.text_raw,
                is_target=m.id == target.id,
            )
            for m, name in [*reversed(before), *after]
        ],
    )


@router.post("/{wa_group_id}/import", response_model=ImportResponse)
async def import_export(
    wa_group_id: str,
    file: UploadFile,
    name: str | None = None,
    Session=Depends(get_session_factory),
    models: Models = Depends(get_models),
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise APIError(413, "FILE_TOO_LARGE", "Export must be under 20 MB")
    # Kept in memory only; the raw export is never written to disk (TRD §6.3).
    content = raw.decode("utf-8-sig", errors="replace")
    with Session() as s:
        try:
            res = import_chat(s, wa_group_id, content, name=name)
        except ParseError as e:
            raise APIError(422, "UNPARSEABLE_EXPORT", str(e)) from e
        chunks = index_group(s, res.group_id, models.embeddings, models.chroma_dir)
    return ImportResponse(group_id=res.group_id, new_messages=res.new_messages, chunks=chunks)


@router.post("/{wa_group_id}/ask", response_model=AskResponse)
def ask(
    wa_group_id: str,
    body: AskRequest,
    Session=Depends(get_session_factory),
    models: Models = Depends(get_models),
):
    started = time.perf_counter()
    with Session() as s:
        group, user = resolve_member(s, wa_group_id, body.user_id)
        group_id, user_pk = group.id, user.id

    chain = build_ask_chain(
        session_factory=Session,
        group_id=group_id,
        embeddings=models.embeddings,
        reranker=models.reranker,
        answer_llm=models.answer_llm,
        rewriter=models.rewriter,
        chroma_dir=models.chroma_dir,
    )
    out = chain.invoke({"question": body.question})
    latency_ms = int((time.perf_counter() - started) * 1000)

    with Session() as s:
        # Chunk ids, not chat text, go into the log (TRD §10).
        s.add(
            QueryLog(
                group_id=group_id,
                user_id=user_pk,
                query=body.question,
                intent="ask",
                filters=json.dumps(out["interpreted_range"]),
                retrieved_chunk_ids=json.dumps(out["chunk_ids"]),
                answer=out["answer"],
                latency_ms=latency_ms,
                model=get_settings().llm_model,
                prompt_version=out["prompt_version"],
            )
        )
        s.commit()
    return AskResponse(
        answer=out["answer"],
        found=out["found"],
        interpreted_range=out["interpreted_range"],
        sources=out["sources"],
        latency_ms=latency_ms,
        trace={**out["trace"], "latency_ms": latency_ms},
    )
