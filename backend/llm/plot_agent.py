from langchain_core.messages import SystemMessage, HumanMessage
from backend.llm.llm_instance import get_llm_instance
from models.messages import PlotCodeOutput
import os
import yaml
from typing import Dict, Any


def load_prompts() -> Dict[str, Any]:
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_plot_code(instructions: str, context: Dict[str, Any]) -> PlotCodeOutput:
    """Calls a specialized LLM to generate plotting code based on instructions."""
    llm = get_llm_instance(structured_output_model=PlotCodeOutput)

    all_prompts = load_prompts()
    system_msg = SystemMessage(content=all_prompts["agent_prompts"]["plot_agent"])

    user_content = (
        f"Instructions: {instructions}\n\n"
        f"Context:\n"
        f"Filename: {context['filename']}\n"
        f"Columns: {context['columns']}\n"
        f"Preview: {context['preview']}"
    )
    user_msg = HumanMessage(content=user_content)

    return llm.invoke([system_msg, user_msg])
