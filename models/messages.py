from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str

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
