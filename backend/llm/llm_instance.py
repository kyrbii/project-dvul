import os
import logging
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

def get_llm_instance(local: bool = False, model_name: str | None = None, api_key: str | None = None, **kwargs):
    """
    Returns a configured LangChain LLM instance.
    If local=True, uses local Ollama; otherwise, uses OpenRouter.
    """
    if local:
        # Local Ollama
        model = model_name or os.getenv("OLLAMA_MODEL")
        if not model:
            raise RuntimeError("OLLAMA_MODEL must be set in the environment.")

        logger.debug(f"Using local Ollama model: {model}")
        return ChatOllama(model=model, **kwargs)
    else:
        # Remote OpenRouter
        model = model_name or os.getenv("OPENROUTER_MODEL")
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not model or not api_key:
            raise RuntimeError("OPENROUTER_MODEL and OPENROUTER_API_KEY must be set in the environment.")
        
        logger.debug(f"Using remote OpenRouter model: {model}")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            default_headers={
                "HTTP-Referer": os.getenv("OR_REFERER", "http://localhost:3000"),
                "X-Title": os.getenv("OR_TITLE", "Uni_Agent_Project"),
            },
            **kwargs
        )