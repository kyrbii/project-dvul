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
from backend.llm.plot_agent import get_plot_code
from backend.llm.sandbox import execute_plot_code
import yaml

langchain.debug = True
# --- Utility Functions ---



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

    @tool
    def generate_description(dummy: str = "") -> str:
        """
        Generates a human-like overview description of the dataset using AI.
        Creates a natural language summary that describes what the data represents.
        """
        print("DEBUG: Agent calling 'generate_description'")
        
        # Gather key metadata
        filename = context.get('filename', 'Unknown')
        num_rows = df.shape[0]
        num_cols = df.shape[1]
        columns_list = list(df.columns)
        dtypes = df.dtypes.to_dict()
        missing_count = df.isnull().sum().sum()
        sample_data = df.head(3).to_string()
        
        # Use LLM to generate human-like description
        llm = get_agent()
        prompt = f"""
        Write a concise, human-like overview description of this dataset. Make it sound natural and informative, like a data analyst describing the dataset to a colleague.

        Dataset Details:
        - Filename: {filename}
        - Size: {num_rows:,} rows, {num_cols} columns
        - Columns: {', '.join(columns_list)}
        - Data types: {', '.join([f'{col}: {dtype}' for col, dtype in dtypes.items()])}
        - Missing values: {missing_count:,} total
        - Sample data:
        {sample_data}

        Write 2-3 paragraphs describing what this dataset appears to be about, what kind of analysis it might support, and any notable characteristics. Use natural language, not bullet points.
        """
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            description = response.content.strip()
        except Exception as e:
            print(f"DEBUG: LLM description generation failed: {e}")
            # Fallback to basic description
            description = f"This is a dataset named {filename} with {num_rows:,} rows and {num_cols} columns. It contains data about {', '.join(columns_list[:3])}{' and more' if len(columns_list) > 3 else ''}. The dataset has {missing_count:,} missing values and appears ready for analysis."
        
        # Store in chat_store
        chat_store["description"] = description
        print("DEBUG: Description stored in chat_store")
        
        return f"Dataset description generated and stored: {description[:100]}..."

    return [
        query_dataframe, 
        get_dataframe_info, 
        get_dataframe_summary, 
        get_unique_values, 
        get_correlations, 
        get_missing_values, 
        generate_plot,
        generate_description
    ]

def _force_final_answer(llm: ChatNVIDIA, question: str, intermediate_steps: list) -> str:
    """
    Called when the agent hits max_iterations without producing a final answer.
    Extracts key insights from intermediate steps and asks LLM to provide a direct answer.
    """
    # Extract insights from observations, not tool names/calls
    key_findings = []
    for action, observation in intermediate_steps:
        obs_text = str(observation)
        # Keep only the most useful part, avoid technical details
        if len(obs_text) > 500:
            obs_text = obs_text[:500] + "..."
        key_findings.append(obs_text)

    findings_text = "\n".join(key_findings[-5:]) if key_findings else "No findings available."

    forced_prompt = (
        f"User Question: {question}\n\n"
        f"Analysis Results:\n{findings_text}\n\n"
        "Write a clear, direct answer to the user's question starting with 'SUMMARY:'. "
        "Focus on answering their question using the analysis results above. "
        "Do not explain the analysis process or tools used. "
        "Reference any plots that were created (e.g., 'See Plot #1'). "
        "Keep it professional and concise in Markdown format."
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

    # 4. Detect first-run
    is_first_run = len(history.messages) == 0
    first_run_instructions = ""

    all_prompts = load_prompts()
    if is_first_run:
        first_run_instructions = "\n" + all_prompts["agent_prompts"].get("first_run_prompt", "")

    # 5. Prepare Prompt
    sys_prompt = all_prompts["agent_prompts"]["analyst_agent"].format(
        filename=tool_context["filename"],
        rows=df.shape[0],
        columns=tool_context["columns"],
        preview=tool_context["preview"],
        first_run_instructions=first_run_instructions
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # 6. Initialize Agent
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
        
        # Check if output contains SUMMARY and extract it
        if "SUMMARY:" in output.upper():
            summary_index = output.upper().find("SUMMARY:")
            output = output[summary_index:]
        else:
            # Check if it's incomplete and needs forced final answer
            is_incomplete = (
                not output
                or "agent stopped" in output.lower()
                or output.strip().startswith(("I need to", "I should", "Let me", "Now "))
            )
            if is_incomplete:
                output = _force_final_answer(llm, message, response.get("intermediate_steps", []))
    except Exception as e:
        output = f"I encountered an error while analyzing the data: {str(e)}"
    
    # 7. Update History
    if message:
        history.add_user_message(message)
    history.add_ai_message(output)
    
    return chat_store, output
