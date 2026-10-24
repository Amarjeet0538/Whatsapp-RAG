import pytest

from app.config import Settings
from app.llm import get_chat_model, get_reranker


def test_chat_model_without_api_key_fails_fast():
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        get_chat_model(Settings(google_api_key=""))


def test_chat_model_uses_configured_model_and_retries():
    llm = get_chat_model(
        Settings(google_api_key="test-key", llm_model="gemini-x", llm_max_retries=3)
    )
    assert llm.model.endswith("gemini-x")
    assert llm.max_retries == 3


def test_reranker_disabled_returns_none():
    assert get_reranker(Settings(reranker_enabled=False)) is None
