from typing import Any, Dict, List
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


class SimpleMessageHistory:
    """A lightweight, JSON-serializable session history manager that avoids langchain-community."""

    def __init__(self, store: Dict[str, Any]):
        self.store = store
        if "messages" not in store:
            store["messages"] = []

    @property
    def messages(self) -> List[BaseMessage]:
        messages_list = []
        for msg in self.store["messages"]:
            if isinstance(msg, dict):
                msg_type = msg.get("type")
                content = msg.get("content", "")
                if msg_type == "human":
                    messages_list.append(HumanMessage(content=content))
                elif msg_type == "ai":
                    messages_list.append(AIMessage(content=content))
            elif isinstance(msg, BaseMessage):
                messages_list.append(msg)
        return messages_list

    def add_user_message(self, message: str) -> None:
        self.store["messages"].append({"type": "human", "content": message})

    def add_ai_message(self, message: str) -> None:
        self.store["messages"].append({"type": "ai", "content": message})


def get_session_history(store: Dict[str, Any]) -> SimpleMessageHistory:
    return SimpleMessageHistory(store)
