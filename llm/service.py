from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
import json
import os
import dotenv

dotenv.load_dotenv()

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

def get_response(message: str) -> str:
    # Minimal Langchain integration point

    # TODO: Add API key to environment variables
    # TODO: Add model to environment variables
    # TODO: Add temperature to environment variables
    # TODO: Add top_p to environment variables
    # TODO: Add max_completion_tokens to environment variables
    # TODO: Add thinking mode to environment variables
    
    # define the API Client

    client = ChatNVIDIA(
      model=os.getenv("LLM_MODEL"),
      api_key= os.getenv("LLM_API_KEY"),
      temperature=1,
      top_p=1,
      max_completion_tokens=16384,
    )

    # get the response
    response = client.invoke([{"role":"user","content":message}])
      
    return response.content




def get_response_with_file(data: Dict[str, Any]) -> dict:
    # Validate the incoming dictionary against our model
    file_info = FileInfo(**data)
  
    agent = ChatNVIDIA(
      model=os.getenv("LLM_MODEL"),
      api_key= os.getenv("LLM_API_KEY"),
      temperature=0.1,
      top_p=1,
      max_completion_tokens=16384,
      )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are 'DVUL' a helpful assistant, that analyzes data. You will get a preview of a .csv file."
                          "From the header and the first 5 rows, you should be able to understand the data."
                          "Return a Heading and a short description of the data."),
        ("user", "Analyze this file:\n\n"
                 "Filename: {filename}\n"
                 "Total Rows: {rows}\n"
                 "Columns: {columns}\n"
                 "Data Preview: {preview}")
    ])
    
    chain = prompt | agent.with_structured_output(AnalysisOutput)

    # Invoke using the validated Pydantic object attributes
    response = chain.invoke({
        "filename": file_info.filename,
        "rows": file_info.rows,
        "columns": ", ".join(file_info.columns),
        "preview": json.dumps(file_info.preview, indent=2)
    })
    
    # returns a dict with the heading and description
    return response.model_dump()



