from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
import langchain
import os
import pandas as pd
from typing import Dict, Any, Type
import models.messages as models
from backend.llm.plot_agent import get_plot_code
from backend.llm.sandbox import execute_plot_code

langchain.debug = True
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
        max_tokens=16384,
        reasoning_budget=2048,  # Reduced for significantly faster response times
        model_kwargs={"enable_thinking":True},  
    )

# --- Tool Factory ---

def create_analysis_tools(df: pd.DataFrame, context: Dict[str, Any]):
    """
    Factory function to create tools with access to a specific DataFrame and metadata.
    Defining tools here allows them to capture 'df' and 'context' in their closure.
    """

    @tool
    def query_dataframe(code: str) -> str:
        """
        Executes arbitrary Python code on the pandas DataFrame 'df'.
        Use this for complex filtering, grouping, or any logic not covered by other tools.
        Example: "df.groupby('category')['price'].mean()"
        """
        print(f"DEBUG: Agent calling 'query_dataframe' with code: {code}")
        try:
            # We use eval for single expressions; for safety/simplicity we restrict to 'df' and 'pd'
            result = eval(code, {"df": df, "pd": pd})
            print(f"DEBUG: 'query_dataframe' returned result: {str(result)[:100]}...")
            return str(result)
        except Exception as e:
            print(f"DEBUG: 'query_dataframe' error: {str(e)}")
            return f"Error executing code: {str(e)}"

    @tool
    def get_dataframe_info(dummy: str = "") -> str:
        """
        Returns the schema information of the DataFrame, including column names, 
        data types, and number of non-null values.
        """
        import io
        buffer = io.StringIO()
        df.info(buf=buffer)
        return buffer.getvalue()

    @tool
    def get_dataframe_summary(dummy: str = "") -> str:
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

    @tool
    def generate_plot(instructions: str) -> str:
        """
        Generates a visualization (plot) based on your instructions.
        Provide clear instructions like 'Create a histogram of age' or 'Compare salary by department'.
        Returns the path to the saved plot image.
        """
        print(f"DEBUG: Agent requested plot: {instructions}")
        try:
            # 1. Get code from Plot Agent (using captured context)
            plot_data = get_plot_code(instructions, context)
            print(f"DEBUG: Plot Agent generated code for '{plot_data.title}'")
            # 2. Execute code in Sandbox
            result = execute_plot_code(plot_data.code, df)
            print(f"DEBUG: Plot generated at {result}")
            return result
        except Exception as e:
            print(f"DEBUG: generate_plot error: {str(e)}")
            return f"Error generating plot: {str(e)}"

    return [query_dataframe, get_dataframe_info, get_dataframe_summary, get_unique_values, generate_plot]

# --- Main Entry Point ---

def agent_call(chat_store: Dict[str, Any], message: str, response_model: Type[models.T] = None, response_model_raw: bool = True, limit: int = 10, max_iterations: int = 5):
    """
    Main execution function using a tool-calling agent for specialized CSV analysis.
    """
    # 1. Setup context
    history = get_session_history(chat_store)
    df = chat_store["dataframe"]
    llm = get_agent(response_model, response_model_raw)
    
    # 2. Setup Context for Tools
    tool_context = {
        "filename": chat_store["filename"],
        "columns": list(df.columns),
        "preview": df.head(5).to_dict(orient="records")
    }
    
    # 3. Initialize Tools
    tools = create_analysis_tools(df, tool_context)

    # 4. Prepare Prompt
    sys_prompt = os.getenv("LLM_SYS_PROMPT").format(
        filename=tool_context["filename"],
        rows=df.shape[0],
        columns=tool_context["columns"],
        preview=tool_context["preview"]
    ).replace("{", "{{").replace("}", "}}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt + "\nYou have access to tools that can query the full dataset and generate plots. Use them to provide accurate answers."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # 5. Initialize Agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=max_iterations
    )
    
    # 6. Execute
    trimmed_history = history.messages[-limit:] if len(history.messages) > limit else history.messages
    
    try:
        print(f"DEBUG: Starting LLM execution (Thinking/Answering phase)...")
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
