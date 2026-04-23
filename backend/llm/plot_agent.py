from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os
from typing import Dict, Any

class PlotCodeOutput(BaseModel):
    title: str = Field(description="A short title for the plot")
    code: str = Field(description="Self-contained Python code using 'df' and 'plt' to create an SVG plot. Do NOT use plt.show().")

def get_plot_code(instructions: str, context: Dict[str, Any]) -> PlotCodeOutput:
    """
    Calls a specialized LLM to generate plotting code based on instructions.
    """
    llm = ChatNVIDIA(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        temperature=0.1
    ).with_structured_output(PlotCodeOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", os.getenv("LLM_SYS_PROMPT_plots")),
        ("user", "Instructions: {instructions}\n\nContext:\nFilename: {filename}\nColumns: {columns}\nPreview: {preview}")
    ])
    
    chain = prompt | llm
    
    return chain.invoke({
        "instructions": instructions,
        "filename": context["filename"],
        "columns": context["columns"],
        "preview": context["preview"]
    })
