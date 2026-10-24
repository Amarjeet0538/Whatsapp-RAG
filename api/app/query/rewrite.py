from langchain_core.runnables import Runnable, RunnableLambda

from app.models.schemas import Rewrite
from app.prompts import load_prompt


def identity_rewrite(x: dict) -> Rewrite:
    return Rewrite(normalized=x["question"], expansions=[], keywords=[])


def make_rewrite_chain(llm) -> Runnable:
    """prompt | llm.with_structured_output(Rewrite), one retry; falls back to the raw question."""
    prompt, _ = load_prompt("rewrite_v1")
    chain = (prompt | llm.with_structured_output(Rewrite)).with_retry(stop_after_attempt=2)
    return chain.with_fallbacks([RunnableLambda(identity_rewrite)])
