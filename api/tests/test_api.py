import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel
from sqlalchemy import func, select
from tests.conftest import OverlapReranker

from app.db import get_session_factory
from app.deps import Models, get_models
from app.main import app
from app.models.db import Message, QueryLog

KEY = {"X-API-Key": "test-key"}


@pytest.fixture
def client(monkeypatch, Session, bow_embeddings, chroma_dir):
    monkeypatch.setenv("API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    llm = FakeListChatModel(
        responses=["Budget 25000 tak approved hai (Amit Client).\nSOURCES: [1]"]
    )
    app.dependency_overrides[get_session_factory] = lambda: Session
    app.dependency_overrides[get_models] = lambda: Models(
        bow_embeddings, OverlapReranker(), llm, None, chroma_dir
    )
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def upload(client, content: str, group="grp-1"):
    return client.post(
        f"/api/v1/groups/{group}/import",
        headers=KEY,
        files={"file": ("chat.txt", content.encode(), "text/plain")},
    )


def test_requests_without_valid_api_key_rejected(client):
    r = client.post(
        "/api/v1/groups/grp-1/ask",
        json={"question": "x", "user_id": "Riya"},
        headers={"X-API-Key": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_import_then_member_asks_and_query_is_logged(client, sample_chat, Session):
    r = upload(client, sample_chat)
    assert r.status_code == 200 and r.json()["new_messages"] == 49 and r.json()["chunks"] > 0
    r = client.post(
        "/api/v1/groups/grp-1/ask",
        headers=KEY,
        json={"question": "total budget kitna approved hai?", "user_id": "Riya"},
    )
    body = r.json()
    assert r.status_code == 200 and body["found"] is True
    assert body["sources"][0]["sender"] == "Amit Client"
    with Session() as s:
        log = s.scalars(select(QueryLog)).one()
    assert (
        log.query == "total budget kitna approved hai?"
        and log.retrieved_chunk_ids
        and log.prompt_version
    )


def test_non_member_gets_no_group_content(client, sample_chat):
    upload(client, sample_chat)
    r = client.post(
        "/api/v1/groups/grp-1/ask",
        headers=KEY,
        json={"question": "budget kitna hai?", "user_id": "Stranger"},
    )
    assert r.status_code == 403
    assert r.json() == {"error": {"code": "NOT_A_MEMBER", "message": r.json()["error"]["message"]}}


def test_unknown_group_is_404(client):
    r = client.post(
        "/api/v1/groups/nope/ask", headers=KEY, json={"question": "x", "user_id": "Riya"}
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "GROUP_NOT_FOUND"


def test_unparseable_upload_explains_supported_formats(client):
    r = upload(client, "just some notes\nnot a chat\n")
    assert r.status_code == 422
    assert (
        r.json()["error"]["code"] == "UNPARSEABLE_EXPORT"
        and "Android" in r.json()["error"]["message"]
    )


def test_health_reports_components(client):
    body = client.get("/api/v1/health").json()
    assert body["db"] == "ok" and set(body) >= {"status", "db", "vector_store", "llm"}


def test_list_groups_empty_then_after_import(client, sample_chat, Session):
    assert client.get("/api/v1/groups", headers=KEY).json() == []
    upload(client, sample_chat)
    [g] = client.get("/api/v1/groups", headers=KEY).json()
    with Session() as s:
        n = s.scalar(select(func.count(Message.id)).where(Message.is_system.is_(False)))
    assert g["wa_group_id"] == "grp-1" and g["member_count"] == 4 and g["message_count"] == n
    assert g["last_message_ts"].endswith("+05:30")


def test_reimport_is_success_with_zero_new(client, sample_chat):
    upload(client, sample_chat)
    r = upload(client, sample_chat)
    assert r.status_code == 200 and r.json()["new_messages"] == 0


def test_members_sorted_by_message_count(client, sample_chat):
    upload(client, sample_chat)
    body = client.get("/api/v1/groups/grp-1/members", headers=KEY).json()
    assert [m["display_name"] for m in body] == ["Riya", "Rahul", "Priya", "Amit Client"]
    # Media-omitted and deleted messages are system messages, so they don't count
    assert [m["message_count"] for m in body] == [15, 13, 10, 6]


def test_members_unknown_group_404(client):
    r = client.get("/api/v1/groups/nope/members", headers=KEY)
    assert r.status_code == 404 and r.json()["error"]["code"] == "GROUP_NOT_FOUND"


def ask_budget(client, group="grp-1"):
    return client.post(
        f"/api/v1/groups/{group}/ask",
        headers=KEY,
        json={"question": "total budget kitna approved hai?", "user_id": "Riya"},
    ).json()


def chat_ids(Session, wa_group_id="grp-1") -> list[int]:
    from app.models.db import Group

    with Session() as s:
        gid = s.scalar(select(Group.id).where(Group.wa_group_id == wa_group_id))
        return list(
            s.scalars(
                select(Message.id)
                .where(Message.group_id == gid, Message.is_system.is_(False))
                .order_by(Message.ts, Message.id)
            )
        )


def context(client, mid, user="Riya", window=None, group="grp-1"):
    params = {"user_id": user} | ({"window": window} if window else {})
    return client.get(f"/api/v1/groups/{group}/messages/{mid}/context", headers=KEY, params=params)


def test_ask_sources_carry_message_id(client, sample_chat, Session):
    upload(client, sample_chat)
    src = ask_budget(client)["sources"][0]
    with Session() as s:
        assert s.get(Message, src["message_id"]).text_raw.startswith(src["snippet"])


def test_context_window_middle(client, sample_chat, Session):
    upload(client, sample_chat)
    ids = chat_ids(Session)
    body = context(client, ids[19], window=3).json()
    assert body["target_id"] == ids[19]
    assert [m["id"] for m in body["messages"]] == ids[16:23]
    assert [m["is_target"] for m in body["messages"]].count(True) == 1


def test_context_at_chat_start(client, sample_chat, Session):
    upload(client, sample_chat)
    ids = chat_ids(Session)
    msgs = context(client, ids[0]).json()["messages"]
    assert [m["id"] for m in msgs] == ids[:6] and msgs[0]["is_target"]


def test_context_non_member_403(client, sample_chat, Session):
    upload(client, sample_chat)
    r = context(client, chat_ids(Session)[0], user="Stranger")
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_A_MEMBER"


def test_context_other_group_message_404(client, sample_chat, Session):
    upload(client, sample_chat)
    upload(client, sample_chat.replace("Budget", "Kharcha"), group="grp-2")
    r = context(client, chat_ids(Session, "grp-2")[0])
    assert r.status_code == 404 and r.json()["error"]["code"] == "MESSAGE_NOT_FOUND"


def test_context_window_out_of_range_422(client, sample_chat, Session):
    upload(client, sample_chat)
    assert context(client, chat_ids(Session)[0], window=50).status_code == 422


def test_ask_returns_trace(client, sample_chat):
    from app.config import get_settings

    upload(client, sample_chat)
    body = ask_budget(client)
    t = body["trace"]
    assert t["gated"] is False and t["rerank_enabled"] is True
    assert t["min_relevance"] == get_settings().min_relevance
    assert t["latency_ms"] == body["latency_ms"]
    assert any(c["cited"] for c in t["reranked"])
    assert t["retrieval"]["queries"][0]["text"] == "total budget kitna approved hai?"


def test_ask_gated_trace(client, sample_chat, monkeypatch):
    from app.config import get_settings

    upload(client, sample_chat)
    monkeypatch.setenv("MIN_RELEVANCE", "100")
    get_settings.cache_clear()
    body = ask_budget(client)
    assert body["found"] is False and body["trace"]["gated"] is True
    assert body["trace"]["best_score"] < 100


def test_list_endpoints_require_key(client):
    assert client.get("/api/v1/groups").status_code == 401
    assert client.get("/api/v1/groups/grp-1/members").status_code == 401
