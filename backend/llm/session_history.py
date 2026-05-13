from typing import Any, Dict

from langchain_community.chat_message_histories import ChatMessageHistory


def get_session_history(store: Dict[str, Any]) -> ChatMessageHistory:
    if "messages" not in store:
        store["messages"] = ChatMessageHistory()
    return store["messages"]
