import os
from typing import Any, Dict

from langchain_nvidia_ai_endpoints import ChatNVIDIA


def get_llm(model_name: str | None = None, api_key: str | None = None, **kwargs) -> ChatNVIDIA:
    """Create and return an LLM client instance.

    This factory is the right place to centralize model selection and provider logic.
    """
    model = model_name or os.getenv("LLM_MODEL")
    api_key = api_key or os.getenv("LLM_API_KEY")

    if not model or not api_key:
        raise RuntimeError("LLM_MODEL and LLM_API_KEY must be set in the environment.")

    config: Dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
        "top_p": float(os.getenv("LLM_TOP_P", "1")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "16384")),
        "model_kwargs": {
            "reasoning_budget": int(os.getenv("LLM_REASONING_BUDGET", "2048"))
        },
    }
    config.update(kwargs)

    return ChatNVIDIA(**config)
