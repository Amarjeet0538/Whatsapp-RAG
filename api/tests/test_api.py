import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel
from sqlalchemy import select
from tests.conftest import OverlapReranker

from app.db import get_session_factory
from app.deps import Models, get_models
from app.main import app
from app.models.db import QueryLog

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
