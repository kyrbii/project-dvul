import models.messages as models
from typing import Any, Dict

def get_llm_response(chat_store: Dict[str, Any], message: str) -> models.ChatResponse:
    """
    MOCK IMPLEMENTATION for Frontend PoC. 
    Generates a dummy plot and returns immediately.
    """
    # 1. Generate Dummy SVG
    dummy_svg = """
    <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
      <circle cx="100" cy="100" r="80" stroke="green" stroke-width="4" fill="yellow" />
      <text x="50%" y="50%" text-anchor="middle" stroke="#51c5cf" stroke-width="1px" dy=".3em">TEST PLOT</text>
    </svg>
    """

    # 2. Store in chat_store
    if "plots" not in chat_store:
        chat_store["plots"] = []

    plot_entry = {
                "title": "This is a dummy plot title.",
                "svg": dummy_svg
            }

    chat_store["plots"].append(plot_entry)
    plot_index = len(chat_store["plots"])

    # 3. Dummy bot response
    bot_message = f"This is a dummy response. I have generated a test plot for you (Index: {plot_index})."

    return chat_store, models.ChatResponse(
        bot_message=bot_message,
        plot_reference=[plot_index]
    )