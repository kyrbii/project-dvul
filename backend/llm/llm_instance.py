import os
import logging
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

def get_llm_instance(local: bool = False, model_name: str | None = None, api_key: str | None = None, structured_output_model: type | None = None, **kwargs):
    """
    Returns a configured LangChain LLM instance.
    If local=True, uses local Ollama; otherwise, uses OpenRouter.

    If `structured_output_model` is provided, this function will attempt to
    call `.with_structured_output(structured_output_model)` on the returned
    LLM instance. If the LLM wrapper doesn't support that method, a warning
    is logged and the raw LLM is returned.
    """
    if local:
        # Local Ollama
        model = model_name or os.getenv("OLLAMA_MODEL")
        if not model:
            raise RuntimeError("OLLAMA_MODEL must be set in the environment.")

        logger.debug(f"Using local Ollama model: {model}")
        llm = ChatOllama(model=model, **kwargs)
    else:
        # Remote OpenRouter
        model = model_name or os.getenv("OPENROUTER_MODEL")
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not model or not api_key:
            raise RuntimeError("OPENROUTER_MODEL and OPENROUTER_API_KEY must be set in the environment.")
        
        logger.debug(f"Using remote OpenRouter model: {model}")
        llm = ChatOpenAI(
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

    if structured_output_model is not None:
        try:
            # Use JSON mode for maximum compatibility with diverse OpenRouter and OSS models
            llm = llm.with_structured_output(structured_output_model, method="json_mode")
        except Exception as e:
            logger.warning(f"Failed to use json_mode, falling back to default structured output: {e}")
            try:
                llm = llm.with_structured_output(structured_output_model)
            except AttributeError:
                logger.warning("LLM instance does not support with_structured_output(); returning raw LLM")

    return llm