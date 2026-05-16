import io
import logging
import os
from typing import Any, Dict

import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from backend.llm.llm_instance import get_llm_instance
from backend.llm.plot_agent import get_plot_code
from backend.llm.sandbox import execute_plot_code

logger = logging.getLogger(__name__)


def _truncate_activity_value(value: Any, max_length: int = 120) -> str:
    text = str(value)
    return text if len(text) <= max_length else text[:max_length] + "..."


def _record_agent_activity(
    chat_store: Dict[str, Any],
    message: str,
    event_type: str = "tool",
    tool_name: str | None = None,
    tool_args: Dict[str, Any] | None = None,
) -> None:
    next_index = chat_store.setdefault("_activity_next_index", 1)
    activity = chat_store.setdefault("activity", [])
    event = {
        "index": next_index,
        "type": event_type,
        "message": message,
    }
    chat_store["_activity_next_index"] = next_index + 1

    if tool_name:
        event["tool_name"] = tool_name
    if tool_args is not None:
        event["tool_args"] = {
            key: _truncate_activity_value(value)
            for key, value in tool_args.items()
        }

    activity.append(event)


def _save_debug_plot(svg_data: str, title: str, plot_index: int) -> None:
    try:
        debug_dir = "debug_plots"
        os.makedirs(debug_dir, exist_ok=True)
        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        debug_path = os.path.join(debug_dir, f"plot_{plot_index}_{safe_title}.svg")
        with open(debug_path, "w") as f:
            f.write(svg_data)
    except Exception as exc:
        logger.exception(f"Failed to save debug plot: {exc}")


def create_analysis_tools(df: pd.DataFrame, context: Dict[str, Any], chat_store: Dict[str, Any], allowed_tools: list | None = None):
    """Factory for tools that operate on a specific dataframe and chat context."""
    # Define module-level creators so callers can request a subset by name.
    def _make_query_dataframe(df, context, chat_store):
        @tool
        def query_dataframe(code: str) -> str:
            _record_agent_activity(
            chat_store,
            f"Invoking `query_dataframe` with `{{'code': '{_truncate_activity_value(code)}'}}`",
            tool_name="query_dataframe",
            tool_args={"code": code},
            )
            if "\n" in code or "=" in code:
                return "Error: Only single-line expressions without assignments are allowed. Use a single pandas chain."

            logger.debug("Agent calling 'query_dataframe' with code: %s", code)
            try:
                result = eval(code, {"df": df, "pd": pd})
                logger.debug("'query_dataframe' result: %s", str(result)[:100] + '...')
                return str(result)
            except Exception as exc:
                logger.exception(f"Error executing query_dataframe code: {exc}")
                return f"Error executing code: {exc}"

        return query_dataframe

    def _make_get_dataframe_info(df, context, chat_store):
        @tool
        def get_dataframe_info(dummy: str = "") -> str:
            _record_agent_activity(
            chat_store,
            "Invoking `get_dataframe_info` with `{'dummy': ''}`",
            tool_name="get_dataframe_info",
            tool_args={"dummy": dummy},
        )
            buffer = io.StringIO()
            df.info(buf=buffer)
            return buffer.getvalue()

        return get_dataframe_info

    def _make_get_dataframe_summary(df, context, chat_store):
        @tool
        def get_dataframe_summary(dummy: str = "") -> str:
            _record_agent_activity(
            chat_store,
            "Invoking `get_dataframe_summary` with `{'dummy': ''}`",
            tool_name="get_dataframe_summary",
            tool_args={"dummy": dummy},
        )
            return str(df.describe())

        return get_dataframe_summary

    def _make_get_unique_values(df, context, chat_store):
        @tool
        def get_unique_values(column_name: str) -> str:
            _record_agent_activity(
            chat_store,
            f"Invoking `get_unique_values` with `{{'column_name': '{_truncate_activity_value(column_name)}'}}`",
            tool_name="get_unique_values",
            tool_args={"column_name": column_name},
        )
            if column_name not in df.columns:
                return f"Error: Column '{column_name}' not found."
            return str(df[column_name].value_counts().head(10))

        return get_unique_values

    def _make_get_correlations(df, context, chat_store):
        @tool
        def get_correlations(dummy: str = "") -> str:
            _record_agent_activity(
            chat_store,
            "Invoking `get_correlations` with `{'dummy': ''}`",
            tool_name="get_correlations",
            tool_args={"dummy": dummy},
        )
            logger.debug("Agent calling 'get_correlations'")
            numeric_df = df.select_dtypes(include=["number"])
            if numeric_df.empty:
                return "No numerical columns found for correlation analysis."
            return str(numeric_df.corr().round(2))

        return get_correlations

    def _make_get_missing_values(df, context, chat_store):
        @tool
        def get_missing_values(dummy: str = "") -> str:
            _record_agent_activity(
            chat_store,
            "Invoking `get_missing_values` with `{'dummy': ''}`",
            tool_name="get_missing_values",
            tool_args={"dummy": dummy},
        )
            logger.debug("Agent calling 'get_missing_values'")
            missing = df.isnull().sum()
            return str(missing[missing > 0]) if missing.any() else "No missing values detected."

        return get_missing_values

    def _make_generate_plot(df, context, chat_store):
        @tool
        def generate_plot(instructions: str) -> str:
            _record_agent_activity(
            chat_store,
            f"Invoking `generate_plot` with `{{'instructions': '{_truncate_activity_value(instructions)}'}}`",
            tool_name="generate_plot",
            tool_args={"instructions": instructions},
        )
            logger.debug("Agent requested plot: %s", instructions)
            try:
                plot_data = get_plot_code(df, instructions, context, chat_store)
                svg_data = execute_plot_code(plot_data.code, df)

                if svg_data.startswith("Sandbox Error"):
                    return svg_data

                if "plots" not in chat_store:
                    chat_store["plots"] = []

                plot_entry = {"title": plot_data.title, "svg": svg_data}
                chat_store["plots"].append(plot_entry)
                plot_index = len(chat_store["plots"])

                _save_debug_plot(svg_data, plot_data.title, plot_index)

                logger.debug("Plot #%d (%s) generated and stored.", plot_index, plot_data.title)
                return f"Plot successfully generated and stored as Plot #{plot_index}: '{plot_data.title}'"
            except Exception as exc:
                logger.exception(f"Error generating plot: {exc}")
                return f"Error generating plot: {exc}"

        return generate_plot

    def _make_generate_description(df, context, chat_store):
        @tool
        def generate_description(dummy: str = "") -> str:
            _record_agent_activity(
            chat_store,
            "Invoking `generate_description` with `{'dummy': ''}`",
            tool_name="generate_description",
            tool_args={"dummy": dummy},
        )
            logger.debug("Agent calling 'generate_description'")
            filename = context.get("filename", "Unknown")
            num_rows = df.shape[0]
            num_cols = df.shape[1]
            columns_list = list(df.columns)
            dtypes = df.dtypes.to_dict()
            missing_count = df.isnull().sum().sum()
            sample_data = df.head(3).to_string()

            llm = get_llm_instance(local=False)
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
                logger.exception(f"LLM description generation failed: {exc}")
                description = (
                    f"This is a dataset named {filename} with {num_rows:,} rows and {num_cols} columns. "
                    f"It contains data about {', '.join(columns_list[:3])}"
                    f"{' and more' if len(columns_list) > 3 else ''}. "
                    f"The dataset has {missing_count:,} missing values and appears ready for analysis."
                )

            chat_store["description"] = description
            logger.debug("Description stored in chat_store")
            return f"Dataset description generated and stored: {description[:100]}..."

        return generate_description

    # Map of available tool creators so callers can select by name.
    AVAILABLE_TOOL_CREATORS = {
        "query_dataframe": _make_query_dataframe,
        "get_dataframe_info": _make_get_dataframe_info,
        "get_dataframe_summary": _make_get_dataframe_summary,
        "get_unique_values": _make_get_unique_values,
        "get_correlations": _make_get_correlations,
        "get_missing_values": _make_get_missing_values,
        "generate_plot": _make_generate_plot,
        "generate_description": _make_generate_description,
    }

    def get_available_tool_names():
        return list(AVAILABLE_TOOL_CREATORS.keys())

    def create_tools(allowed_tools: list | None = None):
        """Create and return the requested tools for this dataframe/context.

        - allowed_tools: list of names to include (from `get_available_tool_names()`).
          If None, all tools will be returned.
        """
        if allowed_tools is None:
            chosen = AVAILABLE_TOOL_CREATORS.keys()
        else:
            chosen = [name for name in allowed_tools if name in AVAILABLE_TOOL_CREATORS]

        tools = [AVAILABLE_TOOL_CREATORS[name](df, context, chat_store) for name in chosen]
        return tools

    # Return requested tools (or all if `allowed_tools` is None).
    return create_tools(allowed_tools)
