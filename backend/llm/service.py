from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from models.messages import FileInfo, AnalysisOutput, ChatRequest, ChatResponse, FileRequest
import json
import os
from typing import Any, Dict
import dotenv

dotenv.load_dotenv()

def get_response(request: ChatRequest) -> ChatResponse:
  return ChatResponse(
    bot_message="This is a placeholder for the chat without file",
    plot_reference=[]
  )

def get_response(message: str) -> str:
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



def get_response_with_file(request: FileRequest) -> ChatResponse:
  return ChatResponse(
    bot_message="This is a placeholder for the chat with file",
    plot_reference=[]
  )

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



