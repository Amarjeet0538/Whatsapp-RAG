"""Versioned prompt files loaded into ChatPromptTemplate (TRD §2.5.5)."""

from functools import lru_cache
from pathlib import Path

import yaml
from langchain_core.prompts import ChatPromptTemplate


@lru_cache
def load_prompt(name: str) -> tuple[ChatPromptTemplate, str]:
    data = yaml.safe_load((Path(__file__).parent / f"{name}.yaml").read_text())
    prompt = ChatPromptTemplate.from_messages(
        [("system", data["system"]), ("human", data["human"])]
    )
    return prompt, data["version"]
