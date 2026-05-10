import os
from langchain_openai import ChatOpenAI

def get_llm(model_name: str | None = None, api_key: str | None = None, **kwargs) -> ChatOpenAI:
    """
    Returns a configured LangChain LLM instance. 
    Defaults to OpenRouter but remains flexible for other OpenAI-compatible providers.
    """
    
    # 1. Resolve core credentials
    model = model_name or os.getenv("OPENROUTER_MODEL")
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")

    if not model or not api_key:
        raise RuntimeError("LLM_MODEL and LLM_API_KEY must be set in the environment.")

    # 2. Return instance with direct parameter assignment
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        # OpenRouter specific endpoint
        base_url="https://openrouter.ai/api/v1", 
        
        # Core Model Hyperparameters
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        
        # OpenRouter identification headers
        default_headers={
            "HTTP-Referer": os.getenv("OR_REFERER", "http://localhost:3000"),
            "X-Title": os.getenv("OR_TITLE", "Uni_Agent_Project"),
        },
        
        # Allows you to pass extra parameters like 'streaming=True' or 'callbacks' on the fly
        **kwargs 
    )