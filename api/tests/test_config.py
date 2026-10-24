from pathlib import Path

import yaml

from app.config import ROOT, Settings


def test_env_var_overrides_yaml(monkeypatch):
    monkeypatch.setenv("FINAL_TOP_K", "7")
    assert Settings().final_top_k == 7


def test_every_yaml_key_is_a_settings_field():
    keys = set(yaml.safe_load(Path(ROOT / "config.yaml").read_text()))
    assert keys - set(Settings.model_fields) == set()


def test_trd_retrieval_keys_present_in_yaml():
    keys = set(yaml.safe_load(Path(ROOT / "config.yaml").read_text()))
    needed = {
        "reranker_model",
        "rerank_top_n",
        "rrf_k",
        "chroma_dir",
        "min_relevance",
        "max_chunk_tokens",
        "min_chunk_chars",
        "db_url",
        "llm_max_retries",
    }
    assert needed - keys == set()
