import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage

import models.messages as models
from backend.llm.agent_connection import agent_call
from backend.llm.llm_instance import get_llm_instance

logger = logging.getLogger(__name__)


def get_llm_response(
    chat_store: Dict[str, Any], message: str, model: str, local: bool
) -> models.ChatResponse:
    """Coordinates the agent call and returns only the indices of plots generated in this turn."""
    try:
        # Trigger dataset description concurrently in the background if not already present
        if "description" not in chat_store:
            import threading
            threading.Thread(target=get_dataset_description, args=(chat_store, model, local)).start()

        # 1. Track how many plots we have before the call
        initial_plot_count = len(chat_store.get("plots", []))

        # 2. Call the agent
        chat_store, bot_message = agent_call(chat_store, message, model_name=model, local=local)

        # 3. Calculate which plots are new
        current_plot_count = len(chat_store.get("plots", []))
        new_plot_indices = list(
            range(initial_plot_count + 1, current_plot_count + 1)
        )

    except Exception as e:
        logger.exception("Service Error")
        return chat_store, models.ChatResponse(
            bot_message="Error: Could not get response from the LLM. " + str(e),
            plot_reference=[],
        )

    return chat_store, models.ChatResponse(
        bot_message=bot_message, plot_reference=new_plot_indices
    )


def get_dataset_description(chat_store: Dict[str, Any], model_name: str, local: bool) -> str:
    """Returns the dataset description. Generates it directly via the LLM on-demand

    if it's not already cached in the chat_store.
    """
    if "description" in chat_store:
        return chat_store["description"]

    df = chat_store["dataframe"]
    filename = chat_store.get("filename", "Unknown")
    num_rows = df.shape[0]
    num_cols = df.shape[1]
    columns_list = list(df.columns)
    dtypes = df.dtypes.to_dict()
    missing_count = df.isnull().sum().sum()
    sample_data = df.head(3).to_string()

    llm = get_llm_instance(model_name=model_name, local=local)
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
        logger.debug("Generating dataset description on-demand...")
        response = llm.invoke([HumanMessage(content=prompt)])
        description = response.content.strip()
    except Exception as exc:
        logger.exception(f"Direct description generation failed: {exc}")
        description = (
            f"This is a dataset named {filename} with {num_rows:,} rows and {num_cols} columns. "
            f"It contains data about {', '.join(columns_list[:3])}"
            f"{' and more' if len(columns_list) > 3 else ''}. "
            f"The dataset has {missing_count:,} missing values and appears ready for analysis."
        )

    chat_store["description"] = description
    return description