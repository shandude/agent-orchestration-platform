"""Turn an Agent configuration into an executable LangGraph node.

Each node, when invoked by the graph, runs one "turn" of that agent:

1. Build the agent's system prompt from its configurable dimensions
   (role, persona, guardrails, interaction rules, skills).
2. Give it the shared transcript as context (windowed by `memory_window`).
3. Call Gemini with the agent's tools bound for function-calling.
4. Run the tool loop until the agent stops requesting tools (bounded).
5. Record token/cost, persist + broadcast every step, and append the
   agent's final answer to the shared transcript for the next agent.

The node is a closure over the agent snapshot + the run context, so the graph
state stays small and JSON-friendly (just the message transcript).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.models import MessageRole
from app.runtime.context import RunContext
from app.runtime.llm import build_llm, extract_usage
from app.runtime.tools import TOOL_REGISTRY, get_langchain_tools

# Stop a single agent from looping on tools forever within one turn.
_MAX_TOOL_ITERS = 5


def build_system_prompt(agent: dict[str, Any]) -> str:
    """Compose a rich system prompt from the agent's configurable fields."""
    parts: list[str] = []
    name = agent.get("name", "Agent")
    role = agent.get("role", "")
    parts.append(f"You are {name}" + (f", {role}." if role else "."))

    if agent.get("system_prompt"):
        parts.append(agent["system_prompt"])

    skills = agent.get("skills") or []
    if skills:
        parts.append("Your skills: " + ", ".join(skills) + ".")

    if agent.get("interaction_rules"):
        parts.append("Interaction rules: " + agent["interaction_rules"])

    guardrails = agent.get("guardrails") or []
    if guardrails:
        rules = "\n".join(f"- {g}" for g in guardrails)
        parts.append("You MUST always obey these guardrails:\n" + rules)

    tools = agent.get("tools") or []
    if tools:
        parts.append(
            "You can call tools when helpful. Available: " + ", ".join(tools) + "."
        )

    parts.append(
        "When you are part of a multi-agent workflow, read the prior messages "
        "for context, do your part, and produce a clear, self-contained result "
        "the next agent (or the user) can act on."
    )
    return "\n\n".join(parts)


def _text_of(content: Any) -> str:
    """Normalise an LLM message's content to a plain string.

    Newer Gemini models (2.5+) can return `content` as a list of typed parts
    (e.g. [{'type': 'text', 'text': '...'}, ...]) rather than a bare string.
    We flatten that to text so it persists cleanly and routes correctly.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for part in content:
            if isinstance(part, str):
                out.append(part)
            elif isinstance(part, dict):
                out.append(part.get("text") or part.get("content") or "")
        return "".join(out)
    return str(content)


def _render_history(history: list[BaseMessage]) -> str:
    """Render the shared transcript as attributed lines for context.

    Each message becomes `Name: text` (or `User: ...` for the human), so the
    next agent can see who said what without us replaying raw AIMessages (which
    would confuse the model about whose turn it is).
    """
    lines: list[str] = []
    for m in history:
        text = _text_of(getattr(m, "content", "")).strip()
        if not text:
            continue
        if isinstance(m, HumanMessage):
            who = "User"
        elif isinstance(m, AIMessage):
            who = getattr(m, "name", None) or "Assistant"
        else:
            continue  # skip tool/system noise in the cross-agent view
        lines.append(f"{who}: {text}")
    return "\n".join(lines)


def _execute_tool_call(tool_call: dict[str, Any]) -> str:
    name = tool_call.get("name", "")
    args = tool_call.get("args", {}) or {}
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return f"[unknown tool: {name}]"
    try:
        return str(spec.func(**args))
    except Exception as exc:  # noqa: BLE001
        return f"[tool {name} error: {exc}]"


def make_agent_node(
    node_id: str,
    agent: dict[str, Any],
    ctx: RunContext,
) -> Callable[[dict], Awaitable[dict]]:
    """Return an async node function for the given agent snapshot."""

    model_name = agent.get("model") or "gemini-2.5-flash"
    temperature = float(agent.get("temperature", 0.3))
    max_tokens = int(agent.get("max_tokens", 1024))
    memory_window = int(agent.get("memory_window", 10))
    tool_names = agent.get("tools") or []

    base_llm = build_llm(model_name, temperature, max_tokens)
    lc_tools = get_langchain_tools(tool_names)
    llm = base_llm.bind_tools(lc_tools) if lc_tools else base_llm

    async def node(state: dict) -> dict:
        await ctx.log(
            "node_start",
            f"{agent.get('name', node_id)} is thinking…",
            data={"node_id": node_id, "agent_name": agent.get("name")},
        )

        system = SystemMessage(content=build_system_prompt(agent))
        history: list[BaseMessage] = list(state.get("messages", []))
        if memory_window > 0:
            history = history[-memory_window:]

        # Flatten the shared transcript into ONE human-framed context turn.
        #
        # Why: in a multi-agent graph the transcript usually ends on a previous
        # agent's AIMessage. If we replayed that directly, Gemini would see "the
        # assistant already answered" and return an empty turn. Instead we render
        # the conversation so far as labelled context inside a HumanMessage, so
        # every agent always receives a turn that ends on human input and is
        # prompted to actually produce its contribution.
        convo = _render_history(history)
        prompt = (
            f"Conversation so far:\n{convo}\n\n"
            f"You are {agent.get('name', node_id)}. Provide your contribution now."
            if convo
            else "Begin the task."
        )
        working: list[BaseMessage] = [system, HumanMessage(content=prompt)]

        # ── tool loop ────────────────────────────────────────────────
        final: AIMessage | None = None
        for _ in range(_MAX_TOOL_ITERS):
            response: AIMessage = await llm.ainvoke(working)
            usage = extract_usage(model_name, response)

            tool_calls = getattr(response, "tool_calls", None) or []
            if tool_calls:
                # Record the LLM's "I want to call tools" turn (cost counts).
                await ctx.record_message(
                    MessageRole.agent,
                    _text_of(response.content) or f"(calling {len(tool_calls)} tool(s))",
                    agent_id=agent.get("id"),
                    agent_name=agent.get("name"),
                    usage=usage,
                )
                working.append(response)
                for call in tool_calls:
                    await ctx.log(
                        "tool_call",
                        f"{agent.get('name')} → {call.get('name')}({call.get('args')})",
                        data={"tool": call.get("name"), "args": call.get("args")},
                    )
                    result = _execute_tool_call(call)
                    await ctx.record_message(
                        MessageRole.tool,
                        f"{call.get('name')}: {result}",
                        agent_name=call.get("name"),
                    )
                    working.append(
                        ToolMessage(content=result, tool_call_id=call.get("id", ""))
                    )
                continue  # let the agent react to tool results

            # No tool calls → this is the agent's final answer for the turn.
            final = response
            await ctx.record_message(
                MessageRole.agent,
                _text_of(response.content),
                agent_id=agent.get("id"),
                agent_name=agent.get("name"),
                usage=usage,
            )
            break

        text = _text_of(final.content) if final else ""
        await ctx.log(
            "node_end",
            f"{agent.get('name', node_id)} finished.",
            data={"node_id": node_id},
        )

        # Append this agent's answer to the shared transcript (named, so other
        # agents and the UI can attribute it), and expose it for edge routing.
        labelled = AIMessage(content=text, name=agent.get("name", node_id))
        return {
            "messages": [labelled],
            "last_output": text,
            "agent_outputs": {node_id: text},
        }

    return node
