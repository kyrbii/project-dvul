from functools import lru_cache
import os
import logging
from typing import Dict, Any, List, TypedDict
import yaml
import pandas as pd
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from backend.llm.llm_instance import get_llm_instance
from models.messages import PlotCodeOutput
from backend.llm.sandbox import execute_plot_code
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


@lru_cache()
def load_prompts() -> Dict[str, Any]:
    """Loads prompt templates from yaml file. Cached to avoid reading disk multiple times."""
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


class PlottingState(TypedDict):
    """LangGraph state representation for the plotting sub-agent."""
    instructions: str
    context: Dict[str, Any]
    model: str
    local: bool
    messages: List[BaseMessage]
    code: str
    title: str
    error: str | None
    svg: str | None
    attempts: int
    df: Any


def generate_code_node(state: PlottingState) -> Dict[str, Any]:
    """LLM Node: Generates python plotting code based on instructions and current state/history."""
    llm = get_llm_instance(
        structured_output_model=PlotCodeOutput,
        model_name=state["model"],
        local=state["local"]
    )
    
    messages = list(state.get("messages", []))
    if not messages:
        # Initial run: Load prompts & context
        all_prompts = load_prompts()
        system_msg = SystemMessage(content=all_prompts["agent_prompts"]["plot_agent"])
        
        # Check if modifying/improving an existing plot
        prev_code = state["context"].get("previous_code")
        if prev_code:
            user_content = (
                f"You are modifying/improving an existing plot.\n"
                f"Here is the previous code:\n```python\n{prev_code}\n```\n\n"
                f"Instructions for modification: {state['instructions']}\n\n"
                f"Context:\n"
                f"Filename: {state['context']['filename']}\n"
                f"Columns: {state['context']['columns']}\n"
                f"Preview: {state['context']['preview']}"
            )
        else:
            user_content = (
                f"Instructions: {state['instructions']}\n\n"
                f"Context:\n"
                f"Filename: {state['context']['filename']}\n"
                f"Columns: {state['context']['columns']}\n"
                f"Preview: {state['context']['preview']}"
            )
        user_msg = HumanMessage(content=user_content)
        messages = [system_msg, user_msg]
    else:
        # Error correction run: Feed back the error
        messages.append(AIMessage(content=f"Title: {state['title']}\nCode:\n{state['code']}"))
        messages.append(HumanMessage(content=(
            f"The code execution failed with the following error:\n{state['error']}\n\n"
            f"Please correct the code and try again. Ensure all variables are defined, "
            f"column names exist and are correct based on the dataset schema, "
            f"and only standard matplotlib/pandas/seaborn/numpy operations are used."
        )))

    try:
        output: PlotCodeOutput = llm.invoke(messages)
        return {
            "messages": messages,
            "code": output.code,
            "title": output.title,
            "attempts": state.get("attempts", 0) + 1,
        }
    except Exception as exc:
        logger.exception("Error calling LLM in plotting node")
        return {
            "messages": messages,
            "error": f"LLM Invocation Error: {exc}",
            "attempts": state.get("attempts", 0) + 1,
        }


def execute_code_node(state: PlottingState) -> Dict[str, Any]:
    """Sandbox Node: Executes the generated plot code in a hardened environment."""
    df = state["df"]
    
    # If LLM invocation itself failed, skip execution and return the error
    if state.get("error") and state["error"].startswith("LLM Invocation"):
        return {}
        
    svg_data = execute_plot_code(state["code"], df)
    if svg_data.startswith("Sandbox Error") or svg_data.startswith("Error"):
        return {"error": svg_data, "svg": None}
    else:
        return {"error": None, "svg": svg_data}


def should_continue(state: PlottingState) -> str:
    """Router: Evaluates whether the generated code needs error correction retries."""
    if state.get("error") is None:
        return "end"
    if state.get("attempts", 0) >= 3:
        logger.warning("Plot agent reached max correction attempts.")
        return "end"
    return "generate"


# Compile the LangGraph
workflow = StateGraph(PlottingState)
workflow.add_node("generate", generate_code_node)
workflow.add_node("execute", execute_code_node)

workflow.set_entry_point("generate")
workflow.add_edge("generate", "execute")
workflow.add_conditional_edges(
    "execute",
    should_continue,
    {
        "generate": "generate",
        "end": END
    }
)
plotting_graph = workflow.compile()


class PlotCodeResult(BaseModel):
    title: str
    code: str
    svg: str | None = None
    error: str | None = None


def get_plot_code(
    instructions: str,
    context: Dict[str, Any],
    model: str,
    local: bool,
    df: pd.DataFrame
) -> PlotCodeResult:
    """Calls a specialized self-correcting LangGraph agent to generate and execute plotting code."""
    initial_state = {
        "instructions": instructions,
        "context": context,
        "model": model,
        "local": local,
        "messages": [],
        "code": "",
        "title": "Untitled Plot",
        "error": None,
        "svg": None,
        "attempts": 0,
        "df": df,
    }
    
    logger.debug("Invoking plotting LangGraph workflow...")
    final_state = plotting_graph.invoke(initial_state)
    
    return PlotCodeResult(
        title=final_state["title"],
        code=final_state["code"],
        svg=final_state["svg"],
        error=final_state["error"],
    )
