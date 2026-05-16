from langchain_core.prompts import ChatPromptTemplate
from models.messages import PlotCodeOutput
from backend.llm.llm_instance import get_llm_instance
from backend.llm.tools import create_analysis_tools

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
import pandas as pd
import os
import yaml
from typing import Dict, Any

def load_prompts():
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_plot_code(dataframe: pd.DataFrame, instructions: str, context: Dict[str, Any], chat_store: Dict[str, Any]) -> PlotCodeOutput:
    """
    Calls a specialized LLM to generate plotting code based on instructions.
    """
    llm = get_llm_instance()
    tools = create_analysis_tools(dataframe, context, chat_store, allowed_tools=[
        "query_dataframe",
        "get_dataframe_info",
        "get_dataframe_summary",
        "get_unique_values",
        "get_correlations",
        "get_missing_values",
    ])
    
    all_prompts = load_prompts()
    prompt = ChatPromptTemplate.from_messages([
        ("system", all_prompts["agent_prompts"]["plot_agent"]),
        ("user", "Instructions: {instructions}\n\nContext:\nFilename: {filename}\nColumns: {columns}\nPreview: {preview}")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15,
        early_stopping_method="generate",
        return_intermediate_steps=True,
    )
    
    response = agent_executor.invoke(
        {
            "instructions": instructions,
            "filename": context.get("filename", "Unknown"),
            "columns": context.get("columns", []),
            "preview": context.get("preview", []),
        }
    )
    return response["output"]
