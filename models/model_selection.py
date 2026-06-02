import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List

from models.messages import APIModels

logger = logging.getLogger(__name__)

models = [
    APIModels(
        short_name="Nemotron 3 120B",
        long_name="nvidia/nemotron-3-super-120b-a12b:free", 
        local=False, 
        paid=False
    ),
    APIModels(
        short_name="GPT OSS 120B",
        long_name="openai/gpt-oss-120b:free", 
        local=False, 
        paid=False
    ),
    APIModels(
        short_name="Gemma 4",
        long_name="gemma4", 
        local=True, 
        paid=False
    )
]


def check_model_availability(model: APIModels, timeout: float = 4.0) -> bool:
    """Checks if a given model is available by attempting a lightweight inference call."""
    from backend.llm.llm_instance import get_llm_instance
    from langchain_core.messages import HumanMessage
    try:
        llm = get_llm_instance(
            local=model.local, 
            model_name=model.long_name, 
            timeout=timeout
        )
        llm.invoke([HumanMessage(content="ping")])
        return True
    except Exception as e:
        logger.warning(f"Availability check failed for model {model.short_name}: {e}")
        return False


def get_working_models(timeout: float = 8.0) -> List[APIModels]:
    """Checks all defined models in parallel and returns only the ones that are working."""
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        results = executor.map(lambda m: check_model_availability(m, timeout), models)
    return [m for m, is_available in zip(models, results) if is_available]