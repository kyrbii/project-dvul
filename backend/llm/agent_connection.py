import logging
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from backend.llm.llm_instance import get_llm_instance
from backend.llm.session_history import get_session_history
from backend.llm.tools import create_analysis_tools

from backend.llm.plot_agent import load_prompts

logger = logging.getLogger(__name__)


def _force_final_answer_from_messages(llm: Any, question: str, messages: list) -> str:
    key_findings = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            obs_text = str(msg.content)
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

    logger.debug("Agent hit iteration limit or returned incomplete result — forcing final answer via direct LLM call.")
    response = llm.invoke([HumanMessage(content=forced_prompt)])
    return response.content


def agent_call(chat_store: Dict[str, Any], message: str, limit: int = 10, max_iterations: int = 15, model_name : str = None, local : bool = None):
    history = get_session_history(chat_store)
    df = chat_store["dataframe"]
    llm = get_llm_instance(model_name=model_name, local=local)

    tool_context = {
        "filename": chat_store.get("filename", "Unknown"),
        "columns": list(df.columns),
        "preview": df.head(5).to_dict(orient="records"),
    }

    if "plots" not in chat_store:
        chat_store["plots"] = []

    tools = create_analysis_tools(df, tool_context, chat_store, model_name=model_name, local=local)
    all_prompts = load_prompts()

    is_first_run = len(history.messages) == 0
    first_run_instructions = ""
    if is_first_run:
        first_run_instructions = "\n" + all_prompts["agent_prompts"].get("first_run_prompt", "")

    sys_prompt = all_prompts["agent_prompts"]["analyst_agent"].format(
        filename=tool_context["filename"],
        rows=df.shape[0],
        columns=tool_context["columns"],
        preview=tool_context["preview"],
        first_run_instructions=first_run_instructions,
    )

    prompt = SystemMessage(content=sys_prompt)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
    )

    trimmed_history = history.messages[-limit:] if len(history.messages) > limit else history.messages

    user_msg_content = message or "Give me a summary of the data."
    input_messages = list(trimmed_history) + [HumanMessage(content=user_msg_content)]

    # Map max_iterations to a safe recursion limit (2 steps per react agent loop)
    recursion_limit = 2 * max_iterations + 2

    try:
        logger.debug("Starting LangGraph react agent execution...")
        result = agent.invoke(
            {"messages": input_messages},
            config={"recursion_limit": recursion_limit}
        )

        final_msg = result["messages"][-1]
        output = final_msg.content

        if "SUMMARY:" in output.upper():
            summary_index = output.upper().find("SUMMARY:")
            output = output[summary_index:]
        else:
            is_incomplete = (
                not output
                or output.strip().startswith(("I need to", "I should", "Let me", "Now "))
            )
            if is_incomplete:
                output = _force_final_answer_from_messages(llm, user_msg_content, result["messages"])
    except Exception as exc:
        logger.exception("Error while analyzing the data via LangGraph react agent")
        output = f"I encountered an error while analyzing the data: {exc}"

    if message:
        history.add_user_message(message)
    history.add_ai_message(output)

    return chat_store, output
