from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
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
    llm = ChatNVIDIA(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        temperature=0.1
    ).with_structured_output(PlotCodeOutput)
    
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
