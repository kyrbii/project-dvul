import models.messages as models
from backend.llm.llm_connection import agent_call
from typing import Any, Dict



def get_llm_response(chat_store: Dict[str, Any], message: str) -> models.ChatResponse:
  try:
    chat_store, bot_message = agent_call(chat_store, message, limit = 10)
  except Exception as e:  # ToDo: More specific exception with logging
    print(e)
    return chat_store, models.ChatResponse(
      bot_message="Error: Could not get response from the LLM. Maybe try again."+str(e),
      plot_reference=[]
    )

  return chat_store, models.ChatResponse(
    bot_message=bot_message,
    plot_reference=[]
  )