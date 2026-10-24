"""Model factories (TRD §2.5). Everything that needs a model gets it from here."""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import Settings, get_settings


def get_chat_model(settings: Settings | None = None, **overrides) -> ChatGoogleGenerativeAI:
    s = settings or get_settings()
    if not s.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set; add it to .env")
    params = dict(
        model=s.llm_model,
        api_key=s.google_api_key,
        temperature=s.llm_temperature,
        max_tokens=s.llm_max_tokens,
        thinking_level=s.llm_thinking_level,
        max_retries=s.llm_max_retries,
    )
    params.update(overrides)
    return ChatGoogleGenerativeAI(**params)


def _device_kwargs() -> dict:
    """fp16 on GPU: BGE-M3 and the reranker in fp32 (~2.3 GB each) overflow a 4 GB card."""
    import torch

    if torch.cuda.is_available():
        return {"device": "cuda", "model_kwargs": {"dtype": torch.float16}}
    return {"device": "cpu"}


@lru_cache
def _embeddings(model_name: str, batch_size: int) -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=_device_kwargs(),
        encode_kwargs={"normalize_embeddings": True, "batch_size": batch_size},
    )


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    s = settings or get_settings()
    return _embeddings(s.embed_model, s.embed_batch_size)


@lru_cache
def _reranker(model_name: str):
    import torch
    from langchain_community.cross_encoders import HuggingFaceCrossEncoder

    # Identity activation: scores are raw logits (sigmoid squashes everything near 0),
    # which is the scale `min_relevance` is calibrated on.
    kwargs = _device_kwargs() | {"activation_fn": torch.nn.Identity()}
    return HuggingFaceCrossEncoder(model_name=model_name, model_kwargs=kwargs)


def get_reranker(settings: Settings | None = None):
    """Cross-encoder with a `.score(pairs)` method returning logits, or None when disabled."""
    s = settings or get_settings()
    if not s.reranker_enabled:
        return None
    return _reranker(s.reranker_model)
