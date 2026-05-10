import io
import os
from typing import Any, Dict

import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from backend.llm.llm_instance import get_llm
from backend.llm.plot_agent import get_plot_code
from backend.llm.sandbox import execute_plot_code


def _save_debug_plot(svg_data: str, title: str, plot_index: int) -> None:
    try:
        debug_dir = "debug_plots"
        os.makedirs(debug_dir, exist_ok=True)
        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        debug_path = os.path.join(debug_dir, f"plot_{plot_index}_{safe_title}.svg")
        with open(debug_path, "w") as f:
            f.write(svg_data)
    except Exception as exc:
        print(f"DEBUG: Failed to save debug plot: {exc}")


def create_analysis_tools(df: pd.DataFrame, context: Dict[str, Any], chat_store: Dict[str, Any]):
    """Factory for tools that operate on a specific dataframe and chat context."""

    @tool
    def query_dataframe(code: str) -> str:
        """Execute a single-line pandas expression against the loaded DataFrame."""
        if "\n" in code or "=" in code:
            return "Error: Only single-line expressions without assignments are allowed. Use a single pandas chain."

        print(f"DEBUG: Agent calling 'query_dataframe' with code: {code}")
        try:
            result = eval(code, {"df": df, "pd": pd})
            print(f"DEBUG: 'query_dataframe' result: {str(result)[:100]}...")
            return str(result)
        except Exception as exc:
            print(f"DEBUG: 'query_dataframe' error: {exc}")
            return f"Error executing code: {exc}"

    @tool
    def get_dataframe_info(dummy: str = "") -> str:
        """Return schema and non-null counts for the DataFrame."""
        buffer = io.StringIO()
        df.info(buf=buffer)
        return buffer.getvalue()

    @tool
    def get_dataframe_summary(dummy: str = "") -> str:
        """Return descriptive statistics for numerical DataFrame columns."""
        return str(df.describe())

    @tool
    def get_unique_values(column_name: str) -> str:
        """Return the top unique values and counts for the specified column."""
        if column_name not in df.columns:
            return f"Error: Column '{column_name}' not found."
        return str(df[column_name].value_counts().head(10))

    @tool
    def get_correlations(dummy: str = "") -> str:
        """Return the Pearson correlation matrix for numerical DataFrame columns."""
        print("DEBUG: Agent calling 'get_correlations'")
        numeric_df = df.select_dtypes(include=["number"])
        if numeric_df.empty:
            return "No numerical columns found for correlation analysis."
        return str(numeric_df.corr().round(2))

    @tool
    def get_missing_values(dummy: str = "") -> str:
        """Return a count of missing values for each DataFrame column."""
        print("DEBUG: Agent calling 'get_missing_values'")
        missing = df.isnull().sum()
        return str(missing[missing > 0]) if missing.any() else "No missing values detected."

    @tool
    def generate_plot(instructions: str) -> str:
        """Generate a plot from natural language instructions and store it in the chat session."""
        print(f"DEBUG: Agent requested plot: {instructions}")
        try:
            plot_data = get_plot_code(instructions, context)
            svg_data = execute_plot_code(plot_data.code, df)

            if svg_data.startswith("Sandbox Error"):
                return svg_data

            if "plots" not in chat_store:
                chat_store["plots"] = []

            plot_entry = {"title": plot_data.title, "svg": svg_data}
            chat_store["plots"].append(plot_entry)
            plot_index = len(chat_store["plots"])

            _save_debug_plot(svg_data, plot_data.title, plot_index)

            print(f"DEBUG: Plot #{plot_index} ({plot_data.title}) generated and stored.")
            return f"Plot successfully generated and stored as Plot #{plot_index}: '{plot_data.title}'"
        except Exception as exc:
            print(f"DEBUG: generate_plot error: {exc}")
            return f"Error generating plot: {exc}"

    @tool
    def generate_description(dummy: str = "") -> str:
        """Generate a natural-language description of the dataset using the LLM."""
        print("DEBUG: Agent calling 'generate_description'")
        filename = context.get("filename", "Unknown")
        num_rows = df.shape[0]
        num_cols = df.shape[1]
        columns_list = list(df.columns)
        dtypes = df.dtypes.to_dict()
        missing_count = df.isnull().sum().sum()
        sample_data = df.head(3).to_string()

        llm = get_llm()
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
        except Exception as exc:
            print(f"DEBUG: LLM description generation failed: {exc}")
            description = (
                f"This is a dataset named {filename} with {num_rows:,} rows and {num_cols} columns. "
                f"It contains data about {', '.join(columns_list[:3])}"
                f"{' and more' if len(columns_list) > 3 else ''}. "
                f"The dataset has {missing_count:,} missing values and appears ready for analysis."
            )

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
        generate_description,
    ]
