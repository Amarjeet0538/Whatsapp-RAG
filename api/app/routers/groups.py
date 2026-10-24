import json
import time

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.deps import Models, get_models, require_api_key
from app.errors import APIError
from app.indexing.index import index_group
from app.ingestion.parser import ParseError
from app.ingestion.service import hash_id, import_chat
from app.models.db import Group, Membership, QueryLog, User
from app.models.schemas import AskRequest, AskResponse, ImportResponse
from app.query.chain import build_ask_chain

router = APIRouter(prefix="/groups", dependencies=[Depends(require_api_key)])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def member_ref(user_id: str) -> str:
    """Live senders are WhatsApp ids (contain '@'); imported senders are known by display name."""
    return user_id if "@" in user_id else f"name:{user_id}"


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
        group = s.scalar(select(Group).where(Group.wa_group_id == wa_group_id))
        if group is None:
            raise APIError(404, "GROUP_NOT_FOUND", f"No group {wa_group_id!r}")
        user = s.scalar(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.group_id == group.id,
                User.wa_id_hash == hash_id(member_ref(body.user_id)),
            )
        )
        if user is None:
            raise APIError(403, "NOT_A_MEMBER", "You are not a member of this group")
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
    )
