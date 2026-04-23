from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
import os
import pandas as pd
from typing import Dict, Any, Type
import models.messages as models

# --- Utility Functions ---

def get_session_history(store: Dict[str, Any]):
    if "messages" not in store:
        store["messages"] = ChatMessageHistory()
    return store["messages"]

def get_agent(response_model: Type[models.T] = None, raw: bool = True) -> ChatNVIDIA:
    return ChatNVIDIA(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        temperature=0.1,
        top_p=1,
        max_completion_tokens=16384,
    )

# --- Tool Factory ---

def create_analysis_tools(df: pd.DataFrame):
    """
    Factory function to create tools with access to a specific DataFrame.
    Defining tools here allows them to capture 'df' in their closure.
    """

    @tool
    def query_dataframe(code: str) -> str:
        """
        Executes arbitrary Python code on the pandas DataFrame 'df'.
        Use this for complex filtering, grouping, or any logic not covered by other tools.
        Example: "df.groupby('category')['price'].mean()"
        """
        try:
            # We use eval for single expressions; for safety/simplicity we restrict to 'df' and 'pd'
            result = eval(code, {"df": df, "pd": pd})
            return str(result)
        except Exception as e:
            return f"Error executing code: {str(e)}"

    @tool
    def get_dataframe_info() -> str:
        """
        Returns the schema information of the DataFrame, including column names, 
        data types, and number of non-null values.
        """
        import io
        buffer = io.StringIO()
        df.info(buf=buffer)
        return buffer.getvalue()

    @tool
    def get_dataframe_summary() -> str:
        """
        Returns descriptive statistics for numerical columns (mean, std, min, max, etc.).
        Equivalent to df.describe().
        """
        return str(df.describe())

    @tool
    def get_unique_values(column_name: str) -> str:
        """
        Returns the unique values and their counts for a specific column.
        Useful for understanding categorical data.
        """
        if column_name not in df.columns:
            return f"Error: Column '{column_name}' not found."
        return str(df[column_name].value_counts().head(10))

    return [query_dataframe, get_dataframe_info, get_dataframe_summary, get_unique_values]

# --- Main Entry Point ---

def agent_call(chat_store: Dict[str, Any], message: str, response_model: Type[models.T] = None, response_model_raw: bool = True, limit: int = 10):
    """
    Main execution function using a tool-calling agent for specialized CSV analysis.
    """
    # 1. Setup context
    history = get_session_history(chat_store)
    df = chat_store["dataframe"]
    llm = get_agent(response_model, response_model_raw)
    
    # 2. Initialize Tools
    tools = create_analysis_tools(df)

    # 3. Prepare Prompt
    sys_prompt = os.getenv("LLM_SYS_PROMPT").format(
        filename=chat_store["filename"],
        rows=df.shape[0],
        columns=list(df.columns),
        preview=df.head(5).to_dict(orient="records")
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt + "\nYou have access to tools that can query the full dataset. Use them to provide accurate answers."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # 4. Initialize Agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        handle_parsing_errors=True
    )
    
    # 5. Execute
    trimmed_history = history.messages[-limit:] if len(history.messages) > limit else history.messages
    
    try:
        response = agent_executor.invoke({
            "user_input": message or "Give me a summary of the data.",
            "chat_history": trimmed_history
        })
        output = response["output"]
    except Exception as e:
        output = f"I encountered an error while analyzing the data: {str(e)}"
    
    # 6. Update History
    if message:
        history.add_user_message(message)
    history.add_ai_message(output)
    
    return chat_store, output
