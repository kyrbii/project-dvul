from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from models.messages import FileInfo, AnalysisOutput, ChatRequest, ChatResponse, FileRequest
from backend.llm.llm_connection import agent_call
import json
import os
from typing import Any, Dict
import dotenv

dotenv.load_dotenv()


def get_llm_response(chat_store: Dict[str, Any], message: str) -> ChatResponse:
  try:
    chat_store, response = agent_call(chat_store, message, response_model = AnalysisOutput, response_model_raw = False, limit = 10)
  except Exception as e:  # ToDo: More specific exception with logging
    print(e)
    return chat_store, ChatResponse(
      bot_message="Error: Could not get response from the LLM. Maybe try again."+str(e),
      plot_reference=[]
    )

  return chat_store, ChatResponse(
    bot_message=response.heading + "\n" + response.description,
    plot_reference=[]
  )