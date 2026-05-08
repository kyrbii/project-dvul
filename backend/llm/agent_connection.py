import os
from typing import Any, Dict

import langchain
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

from backend.llm.llm_factory import get_llm
from backend.llm.session_history import get_session_history
from backend.llm.tools import create_analysis_tools

import yaml

langchain.debug = True


def load_prompts() -> Dict[str, Any]:
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _force_final_answer(llm: Any, question: str, intermediate_steps: list) -> str:
    key_findings = []
    for action, observation in intermediate_steps:
        obs_text = str(observation)
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


def agent_call(chat_store: Dict[str, Any], message: str, limit: int = 10, max_iterations: int = 15):
    history = get_session_history(chat_store)
    df = chat_store["dataframe"]
    llm = get_llm()

    tool_context = {
        "filename": chat_store.get("filename", "Unknown"),
        "columns": list(df.columns),
        "preview": df.head(5).to_dict(orient="records"),
    }

    if "plots" not in chat_store:
        chat_store["plots"] = []

    tools = create_analysis_tools(df, tool_context, chat_store)
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

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=max_iterations,
        early_stopping_method="generate",
        return_intermediate_steps=True,
    )

    trimmed_history = history.messages[-limit:] if len(history.messages) > limit else history.messages

    try:
        print("DEBUG: Starting LLM execution (Thinking/Answering phase)...")
        response = agent_executor.invoke(
            {
                "user_input": message or "Give me a summary of the data.",
                "chat_history": trimmed_history,
            }
        )
        output = response["output"]

        if "SUMMARY:" in output.upper():
            summary_index = output.upper().find("SUMMARY:")
            output = output[summary_index:]
        else:
            is_incomplete = (
                not output
                or "agent stopped" in output.lower()
                or output.strip().startswith(("I need to", "I should", "Let me", "Now "))
            )
            if is_incomplete:
                output = _force_final_answer(llm, message, response.get("intermediate_steps", []))
    except Exception as exc:
        output = f"I encountered an error while analyzing the data: {exc}"

    if message:
        history.add_user_message(message)
    history.add_ai_message(output)

    return chat_store, output
