import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List
import os
import requests

from models.messages import APIModels

logger = logging.getLogger(__name__)

models = [
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
    ),
    APIModels(
        short_name="Owl Alpha",
        long_name="openrouter/owl-alpha", 
        local=False, 
        paid=False
    )
]



def check_local_ollama(model_name: str, host: str = "http://localhost:11434", timeout: float = 1.0) -> bool:
    try:
        response = requests.get(f"{host}/api/tags", timeout=timeout)
        if response.status_code != 200:
            return False
            
        local_models = [m["name"] for m in response.json().get("models", [])]
        return any(
            name == model_name or name.startswith(f"{model_name}:") 
            for name in local_models
        )
    except requests.RequestException:
        return False


def check_openrouter_model(model_name: str, timeout: float = 2.0) -> bool:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return False
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(
            "https://openrouter.ai/api/v1/models", 
            headers=headers, 
            timeout=timeout
        )
        if response.status_code != 200:
            return False
            
        available_models = [m["id"] for m in response.json().get("data", [])]
        return model_name in available_models
    except requests.RequestException:
        return False


def check_model_availability(model: APIModels, timeout: float = 4.0) -> bool:
    """Checks if a given model is available by querying API endpoints instead of doing generation."""
    if model.local:
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        is_ok = check_local_ollama(model.long_name, host=ollama_host, timeout=min(2.0, timeout))
        if not is_ok:
            logger.warning(f"Local model check failed for {model.short_name}: Ollama offline or model not found.")
        return is_ok
    else:
        is_ok = check_openrouter_model(model.long_name, timeout=timeout)
        if not is_ok:
            logger.warning(f"Remote model check failed for {model.short_name}: Model offline or invalid API key.")
        return is_ok


def get_working_models(timeout: float = 4.0) -> List[APIModels]:
    """Checks all defined models in parallel and returns only the ones that are working."""
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        results = executor.map(lambda m: check_model_availability(m, timeout), models)
    return [m for m, is_available in zip(models, results) if is_available]