from typing import List, Any, Dict, TypeVar
from pydantic import BaseModel, Field

# featured models:
# ChatRequest, ChatResponse, FileInfo, FileRequest, AnalysisOutput, PlotAction, AnalysisResponse

# Generic Type for any Pydantic model
T = TypeVar("T", bound=BaseModel)

# ToDo: Change to user_message -> change BE code

class APIModels(BaseModel):
    short_name: str = Field(description="Short name of the model")
    long_name: str = Field(description="Long name of the model")
    local: bool = Field(description="Whether the model is local")
    paid: bool = Field(description="Whether the model is paid")

class ChatRequest(BaseModel):
    message: str = Field(description="User message to be displayed in chat and be processed by the LLM")
    chat_id: str | None = None

class ChatResponse(BaseModel):
    bot_message: str = Field(description="Response to the user_message to be displayed in chat")
    plot_reference: List[int] = Field(description="List of plot references to be displayed in chat")

class FileInfo(BaseModel):
    filename: str
    rows: int
    columns: List[str]
    preview: List[Dict[str, Any]]

class FileRequest(BaseModel):
    session_id: str = Field(description="ID of the conversation/chat")
    user_message: str = Field(description="User prompt / description")
    file_info: FileInfo = Field(description="File keyfacts for Analysis by LLM")
    file_preview: List[Dict[str, Any]] = Field(description="File preview for Analysis by LLM")


# Define the output structures (what you want from the LLM)

##### ONLY FOR TESTING
class AnalysisOutput(BaseModel):
    heading: str = Field(description="A professional heading for the dataset")
    description: str = Field(description="A 2-3 sentence summary of the data content")
##### END


class PlotAction(BaseModel):
    title: str = Field(description="A short title for this specific plot")
    code: str = Field(description="Independent Python code using pandas/matplotlib to create the plot. Assume 'df' is already loaded.")

class AnalysisResponse(BaseModel):
    summary: str = Field(description="A brief summary of the overall data findings")
    plots: List[PlotAction] = Field(
        default=[], 
        description="A list of up to 3 independent plotting actions.",
        max_length=3
    )

class PlotCodeOutput(BaseModel):
    title: str = Field(description="A short title for the plot")
    code: str = Field(description="Self-contained Python code using 'df' and 'plt' to create an SVG plot. Do NOT use plt.show().")