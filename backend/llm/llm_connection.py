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


# Should this be here? Maybe the session/chat store should be handled by the function arguments?
store = {}

# return the chat history from the session_id and session store
def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# the llm agent
def get_agent(response_model: Type[T], raw: bool = True) -> ChatNVIDIA:
    return ChatNVIDIA(
      model=os.getenv("LLM_MODEL"),
      api_key= os.getenv("LLM_API_KEY"),
      temperature=0.1,
      top_p=1,
      max_completion_tokens=16384,
      ).with_structured_output(response_model, include_raw=raw)
    

# The main execution Function with History Limiting
def agent_call(request: FileRequest, response_model: Type[T] = AnalysisOutput, response_model_raw: bool = True, limit: int = 10):
    history = get_session_history(request.session_id)

    agent = get_agent(response_model, response_model_raw)
    # agent = get_agent(AnalysisResponse, True)

    if not request.user_message:
        request.user_message = "Give me a summary of the data."
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
        "filename": request.file_info.filename,
        "rows": request.file_info.rows,
        "columns": request.file_info.columns,
        "preview": request.file_preview,
        "user_input": request.user_message,
        "chat_history": trimmed_history
    }
    
    try:
        response = chain.invoke(input_data)
    except Exception as e:  # ToDo: More specific exception with logging
        print(e)
        return e
    
    # Store messages manually because we are using structured output (with include_raw=True)
    if not user_message_empty:
        history.add_user_message(request.user_message)
    history.add_message(response["raw"]) # Stores the LLM's full internal response
    
    return response["parsed"]

