from typing import List, Any, Dict
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_message: str = Field(description="User message to be displayed in chat and be processed by the LLM")

class ChatResponse(BaseModel):
    bot_message: str = Field(description="Response to the user_message to be displayed in chat")
    plot_reference: List[int] = Field(description="List of plot references to be displayed in chat")

# Define the input structure (what your frontend/parser sends)
class FileInfo(BaseModel):
    filename: str
    rows: int
    columns: List[str]
    preview: List[Dict[str, Any]]

# Define the output structure (what you want from the LLM)
class AnalysisOutput(BaseModel):
    heading: str = Field(description="A professional heading for the dataset")
    description: str = Field(description="A 2-3 sentence summary of the data content")
