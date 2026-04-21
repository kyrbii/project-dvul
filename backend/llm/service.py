from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from models.messages import FileInfo, AnalysisOutput, ChatRequest, ChatResponse, FileRequest
from backend.llm.llm_connection import agent_call
import json
import os
from typing import Any, Dict
import dotenv

dotenv.load_dotenv()

### PLACEHOLDER
def get_response(request: ChatRequest) -> ChatResponse:
  return ChatResponse(
    bot_message="This is a placeholder for the chat without file",
    plot_reference=[]
  )

### OLD
def get_response(message: str) -> str:
    client = ChatNVIDIA(
      model=os.getenv("LLM_MODEL"),
      api_key= os.getenv("LLM_API_KEY"),
      temperature=1,
      top_p=1,
      max_completion_tokens=16384,
    )
    response = client.invoke([{"role":"user","content":message}])
    return response.content


### NEW - wrong name, will be replaced
def get_response_with_file(request: FileRequest) -> ChatResponse:
  try:
    response = agent_call(request, response_model = AnalysisOutput, response_model_raw = True, limit = 10)
  except Exception as e:  # ToDo: More specific exception with logging
    print(e)
    return ChatResponse(
      bot_message="Error: Could not get response from the LLM. Maybe try again."+str(e),
      plot_reference=[]
    )

  return ChatResponse(
    bot_message=response.heading + "\n" + response.description,
    plot_reference=[]
  )

### OLD - remove after Testing with new function -> Outsourced to llm_connection.py
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
        ("system", """You are 'DVUL' a helpful assistant, that analyzes data. You will get a preview of a .csv file.
                      From the header and the first 5 rows, you should be able to understand the data.
                      Return a Heading and a short description of the data."""),
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



