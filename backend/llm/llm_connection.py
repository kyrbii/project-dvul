# Gemini
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import trim_messages

# Me
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
from typing import List, Dict, Any, Type
from pydantic import BaseModel, Field
from models.messages import ChatRequest, ChatResponse, FileRequest, AnalysisOutput, PlotAction, AnalysisResponse, T



# return the chat history from the session_id and session store
def get_session_history(store: Dict[str, Any]):
    if "messages" not in store:
        store["messages"] = ChatMessageHistory()
    return store["messages"]

# the llm agent
def get_agent(response_model: Type[T] = None, raw: bool = True) -> ChatNVIDIA:
    agent = ChatNVIDIA(
      model=os.getenv("LLM_MODEL"),
      api_key= os.getenv("LLM_API_KEY"),
      temperature=0.1,
      top_p=1,
      max_completion_tokens=16384,
    )
    if response_model:
        return agent.with_structured_output(response_model, include_raw=raw)
    return agent
    

# The main execution Function with History Limiting
def agent_call(chat_store: Dict[str, Any], message: str, response_model: Type[T] = None, response_model_raw: bool = True, limit: int = 10):
    history = get_session_history(chat_store)
    agent = get_agent(response_model, response_model_raw)

    if not message:
        message = "Give me a summary of the data."
        user_message_empty = True
    else: 
        user_message_empty = False

    prompt = ChatPromptTemplate.from_messages([
        ("system", os.getenv("LLM_SYS_PROMPT")),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
    ])

    chain = prompt | agent
    
    # Logic to limit the history to the last 'n' messages
    # We take the last 'limit' messages to avoid token bloat
    trimmed_history = history.messages[-limit:] if len(history.messages) > limit else history.messages

    # Run the chain
    input_data = {
        "filename": chat_store["filename"],
        "rows": chat_store["dataframe"].shape[0],
        "columns": list(chat_store["dataframe"].columns),
        "preview": chat_store["dataframe"].head(5).to_dict(orient="records"),
        "user_input": message,
        "chat_history": trimmed_history
    }
    
    try:
        response = chain.invoke(input_data)
    except Exception as e:  # ToDo: More specific exception with logging
        print(e)
        return e
    
    # Store messages manually
    if not user_message_empty:
        history.add_user_message(message)
    
    if response_model:
        history.add_message(str(response)) 
        return chat_store, response
    else:
        history.add_message(response)
        return chat_store, response.content

