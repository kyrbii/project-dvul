from langchain_core.prompts import ChatPromptTemplate
from backend.llm.llm_instance import get_llm_instance
from models.messages import PlotCodeOutput
import os
import yaml
from typing import Dict, Any

def load_prompts():
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_plot_code(instructions: str, context: Dict[str, Any]) -> PlotCodeOutput:
    """
    Calls a specialized LLM to generate plotting code based on instructions.
    """
    
    llm = get_llm_instance(structured_output_model=PlotCodeOutput)
    
    all_prompts = load_prompts()
    prompt = ChatPromptTemplate.from_messages([
        ("system", all_prompts["agent_prompts"]["plot_agent"]),
        ("user", "Instructions: {instructions}\n\nContext:\nFilename: {filename}\nColumns: {columns}\nPreview: {preview}")
    ])
    
    chain = prompt | llm
    
    return chain.invoke({
        "instructions": instructions,
        "filename": context["filename"],
        "columns": context["columns"],
        "preview": context["preview"]
    })
