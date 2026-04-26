from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
import langchain
import os
import pandas as pd
from typing import Dict, Any
import models.messages as models
from backend.llm.plot_agent import get_plot_code
from backend.llm.sandbox import execute_plot_code

langchain.debug = True
# --- Utility Functions ---

import yaml

def load_prompts():
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_session_history(store: Dict[str, Any]):
    if "messages" not in store:
        store["messages"] = ChatMessageHistory()
    return store["messages"]

def get_agent() -> ChatNVIDIA:
    return ChatNVIDIA(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"), 
        temperature=0.1,
        top_p=1,
        max_tokens=16384,
        model_kwargs={
            "reasoning_budget": 2048 # Moved here to avoid warning
        },  
    )

# --- Tool Factory ---

def create_analysis_tools(df: pd.DataFrame, context: Dict[str, Any], chat_store: Dict[str, Any]):
    """
    Factory function to create tools with access to a specific DataFrame and metadata.
    Defining tools here allows them to capture 'df', 'context', and 'chat_store' in their closure.
    """

    @tool
    def query_dataframe(code: str) -> str:
        """
        Executes a SINGLE LINE Python pandas expression on the DataFrame 'df'.
        CRITICAL: Only single-line expressions are allowed. No assignments (no '='). 
        No plots. Returns the string result of the expression.
        Example: "df.groupby('category')['price'].mean()"
        """
        # Strictly enforce single line and no assignments
        if "\n" in code or "=" in code:
            return "Error: Only single-line expressions without assignments are allowed. Use a single pandas chain."

        print(f"DEBUG: Agent calling 'query_dataframe' with code: {code}")
        try:
            # We use eval for single expressions; for safety/simplicity we restrict to 'df' and 'pd'
            result = eval(code, {"df": df, "pd": pd})
            print(f"DEBUG: 'query_dataframe' result: {str(result)[:100]}...")
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
    def get_correlations(dummy: str = "") -> str:
        """
        Calculates the Pearson correlation matrix for all numerical columns in the DataFrame.
        Use this to find relationships between variables.
        """
        print("DEBUG: Agent calling 'get_correlations'")
        numeric_df = df.select_dtypes(include=['number'])
        if numeric_df.empty:
            return "No numerical columns found for correlation analysis."
        return str(numeric_df.corr().round(2))

    @tool
    def get_missing_values(dummy: str = "") -> str:
        """
        Returns a report of missing values (NaNs) for each column in the DataFrame.
        """
        print("DEBUG: Agent calling 'get_missing_values'")
        missing = df.isnull().sum()
        return str(missing[missing > 0]) if missing.any() else "No missing values detected."

    @tool
    def generate_plot(instructions: str) -> str:
        """
        The ONLY tool for generating visualizations (plots, charts, histograms).
        Provide clear natural language instructions. This tool will handle all the complex 
        plotting logic and return a confirmation message.
        """
        print(f"DEBUG: Agent requested plot: {instructions}")
        try:
            # 1. Get code from Plot Agent
            plot_data = get_plot_code(instructions, context)
            
            # 2. Execute code in Sandbox (returns SVG string)
            svg_data = execute_plot_code(plot_data.code, df)
            
            if svg_data.startswith("Sandbox Error"):
                return svg_data

            # 3. Store plot in chat_store
            if "plots" not in chat_store:
                chat_store["plots"] = []
            
            plot_entry = {
                "title": plot_data.title,
                "svg": svg_data
            }
            chat_store["plots"].append(plot_entry)
            plot_index = len(chat_store["plots"])
            
            # --- DEBUGGING: Save to Disk ---
            try:
                import os
                debug_dir = "debug_plots"
                os.makedirs(debug_dir, exist_ok=True)
                # Clean title for filename
                safe_title = "".join([c if c.isalnum() else "_" for c in plot_data.title])
                debug_path = os.path.join(debug_dir, f"plot_{plot_index}_{safe_title}.svg")
                with open(debug_path, "w") as f:
                    f.write(svg_data)
                print(f"DEBUG: Plot saved to disk at {debug_path}")
            except Exception as disk_e:
                print(f"DEBUG: Failed to save debug plot: {str(disk_e)}")
            # -------------------------------

            print(f"DEBUG: Plot #{plot_index} ({plot_data.title}) generated and stored.")
            return f"Plot successfully generated and stored as Plot #{plot_index}: '{plot_data.title}'"
        except Exception as e:
            print(f"DEBUG: generate_plot error: {str(e)}")
            return f"Error generating plot: {str(e)}"

    return [
        query_dataframe, 
        get_dataframe_info, 
        get_dataframe_summary, 
        get_unique_values, 
        get_correlations, 
        get_missing_values, 
        generate_plot
    ]

def _force_final_answer(llm: ChatNVIDIA, question: str, intermediate_steps: list) -> str:
    """
    Called when the agent hits max_iterations without producing a final answer.
    Sends all intermediate work to the LLM and asks it to summarize into a coherent reply.
    """
    steps_summary = []
    for action, observation in intermediate_steps:
        steps_summary.append(f"- Tool `{action.tool}` returned: {str(observation)[:300]}")

    steps_text = "\n".join(steps_summary) if steps_summary else "No tool results available."

    forced_prompt = (
        f"The user asked: {question}\n\n"
        f"You gathered the following information:\n{steps_text}\n\n"
        "Based solely on the information above, write a clear, concise final answer "
        "for the user. Do not call any more tools. Do not say you cannot answer. Do it in a Markdown Format."
    )

    print("DEBUG: Agent hit iteration limit — forcing final answer via direct LLM call.")
    response = llm.invoke([HumanMessage(content=forced_prompt)])
    return response.content

# --- Main Entry Point ---

def agent_call(chat_store: Dict[str, Any], message: str, limit: int = 10, max_iterations: int = 15):
    """
    Main execution function using a tool-calling agent for specialized CSV analysis.
    """
    # 1. Setup context
    history = get_session_history(chat_store)
    df = chat_store["dataframe"]
    llm = get_agent()
    
    # 2. Setup Context for Tools
    tool_context = {
        "filename": chat_store["filename"],
        "columns": list(df.columns),
        "preview": df.head(5).to_dict(orient="records")
    }
    
    # 3. Initialize Tools (passing chat_store for persistence)
    if "plots" not in chat_store:
        chat_store["plots"] = []
    tools = create_analysis_tools(df, tool_context, chat_store)

    # 4. Prepare Prompt
    all_prompts = load_prompts()
    sys_prompt = all_prompts["agent_prompts"]["analyst_agent"].format(
        filename=tool_context["filename"],
        rows=df.shape[0],
        columns=tool_context["columns"],
        preview=tool_context["preview"]
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_prompt),
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
        max_iterations=max_iterations,
        early_stopping_method="generate",
        return_intermediate_steps=True
    )
    
    # 6. Execute
    trimmed_history = history.messages[-limit:] if len(history.messages) > limit else history.messages
    
    try:
        print("DEBUG: Starting LLM execution (Thinking/Answering phase)...")
        response = agent_executor.invoke({
            "user_input": message or "Give me a summary of the data.",
            "chat_history": trimmed_history
        })
        output = response["output"]
        is_incomplete = (
            not output
            or "agent stopped" in output.lower()
            or output.strip().startswith(("I need to", "I should", "Let me", "Now "))
        )
        if is_incomplete:
            output = _force_final_answer(llm, message, response.get("intermediate_steps", []))
    except Exception as e:
        output = f"I encountered an error while analyzing the data: {str(e)}"
    
    # 6. Update History
    if message:
        history.add_user_message(message)
    history.add_ai_message(output)
    
    return chat_store, output
