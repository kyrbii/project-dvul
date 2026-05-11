import logging
import models.messages as models
from backend.llm.agent_connection import agent_call
from typing import Any, Dict

logger = logging.getLogger(__name__)

def get_llm_response(chat_store: Dict[str, Any], message: str) -> models.ChatResponse:
  """
  Coordinates the agent call and returns only the indices of plots generated in this turn.
  """
  try:
    # 1. Track how many plots we have before the call
    initial_plot_count = len(chat_store.get("plots", []))
    
    # 2. Call the agent
    chat_store, bot_message = agent_call(chat_store, message)
    
    # 3. Calculate which plots are new
    current_plot_count = len(chat_store.get("plots", []))
    new_plot_indices = list(range(initial_plot_count + 1, current_plot_count + 1))
    
  except Exception as e:
    logger.exception("Service Error")
    return chat_store, models.ChatResponse(
      bot_message="Error: Could not get response from the LLM. " + str(e),
      plot_reference=[]
    )

  return chat_store, models.ChatResponse(
    bot_message=bot_message,
    plot_reference=new_plot_indices
  )