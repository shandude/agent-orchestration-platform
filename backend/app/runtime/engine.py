"""Workflow engine — compile a Workflow into a LangGraph StateGraph and run it.

This is the heart of the platform. A stored Workflow is just data: a list of
nodes (each bound to an agent) and edges (each carrying a condition). The engine
turns that data into an executable `StateGraph`:

* workflow node  → graph node (an agent turn, see `agent_node.py`)
* workflow edge  → graph edge; conditional edges implement branching AND
                   feedback loops (an edge may point back to an earlier node)
* condition types:
    - always   : unconditional transition
    - contains : take this edge if the last output contains a phrase
    - llm      : a tiny router LLM picks among the candidate edges

Runaway feedback loops are bounded by `recursion_limit` (MAX_GRAPH_ITERATIONS),
so a "revise → rewrite → revise" cycle always terminates.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.config import get_settings
from app.database import SessionLocal
from app.models import Agent, MessageRole, Run, RunStatus, Workflow
from app.runtime.agent_node import make_agent_node
from app.runtime.context import RunContext
from app.runtime.events import Event, event_bus
from app.runtime.llm import build_llm


# ── graph state ─────────────────────────────────────────────────────
def _merge_dict(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


class GraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    last_output: str
    agent_outputs: Annotated[dict, _merge_dict]


# ── helpers ─────────────────────────────────────────────────────────
def _agent_snapshot(agent: Agent) -> dict[str, Any]:
    """Detach an Agent into a plain dict (safe to use across threads)."""
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "system_prompt": agent.system_prompt,
        "model": agent.model,
        "tools": list(agent.tools or []),
        "skills": list(agent.skills or []),
        "guardrails": list(agent.guardrails or []),
        "interaction_rules": agent.interaction_rules,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "memory_window": agent.memory_window,
    }


async def _llm_route(last_output: str, edges: list[dict]) -> str | None:
    """Ask a small Gemini call which labelled edge best fits the last output."""
    options = "\n".join(
        f"{i}. target={e['target']} — when: {e['condition'].get('value') or 'default'}"
        for i, e in enumerate(edges)
    )
    prompt = (
        "You are a routing function in an agent workflow. Given the last "
        "output, choose which branch to follow. Reply with ONLY the number.\n\n"
        f"Last output:\n{last_output[:1500]}\n\nOptions:\n{options}\n\nAnswer:"
    )
    try:
        llm = build_llm(temperature=0.0, max_tokens=8)
        resp = await llm.ainvoke(prompt)
        digits = "".join(c for c in (resp.content or "") if c.isdigit())
        if digits:
            idx = int(digits[0])
            if 0 <= idx < len(edges):
                return edges[idx]["target"]
    except Exception:  # noqa: BLE001 — routing must never crash the run
        pass
    return None


def _make_router(out_edges: list[dict]):
    """Build an async routing function for one source node's outgoing edges."""

    async def router(state: GraphState) -> str:
        last = (state.get("last_output") or "")
        low = last.lower()

        # 1) deterministic keyword match wins.
        for e in out_edges:
            cond = e["condition"]
            if cond["type"] == "contains" and cond.get("value", "").lower() in low:
                return e["target"]

        # 2) LLM decision among llm-typed edges.
        llm_edges = [e for e in out_edges if e["condition"]["type"] == "llm"]
        if llm_edges:
            choice = await _llm_route(last, llm_edges)
            if choice:
                return choice

        # 3) fall back to the first unconditional edge.
        for e in out_edges:
            if e["condition"]["type"] == "always":
                return e["target"]

        return END

    return router


def build_graph(workflow: Workflow, agents_by_id: dict[str, Agent], ctx: RunContext):
    """Compile the stored workflow into an executable LangGraph."""
    nodes = workflow.nodes or []
    edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "condition": e.get("condition") or {"type": "always", "value": ""},
        }
        for e in (workflow.edges or [])
    ]
    if not nodes:
        raise ValueError("Workflow has no nodes")

    builder = StateGraph(GraphState)
    valid_ids = set()
    for node in nodes:
        agent = agents_by_id.get(node["agent_id"])
        if agent is None:
            raise ValueError(f"Node {node['id']} references unknown agent")
        builder.add_node(node["id"], make_agent_node(node["id"], _agent_snapshot(agent), ctx))
        valid_ids.add(node["id"])

    entry = workflow.entry_node or nodes[0]["id"]
    builder.set_entry_point(entry)

    # Group edges by source; conditional router per source.
    by_source: dict[str, list[dict]] = {}
    for e in edges:
        if e["source"] in valid_ids and e["target"] in valid_ids:
            by_source.setdefault(e["source"], []).append(e)

    for node in nodes:
        nid = node["id"]
        out = by_source.get(nid, [])
        if not out:
            builder.add_edge(nid, END)  # terminal node
            continue
        targets = {e["target"] for e in out}
        path_map = {t: t for t in targets}
        path_map[END] = END
        builder.add_conditional_edges(nid, _make_router(out), path_map)

    return builder.compile()


# ── public API ──────────────────────────────────────────────────────
def create_run(workflow_id: str, input_text: str, trigger: str) -> str:
    """Insert a Run row up front so we have an id for live monitoring."""
    with SessionLocal() as db:
        run = Run(
            workflow_id=workflow_id,
            status=RunStatus.running,
            trigger=trigger,
            input_text=input_text,
        )
        db.add(run)
        db.commit()
        return run.id


async def execute_run(run_id: str, workflow_id: str, input_text: str) -> str:
    """Execute a previously-created run to completion. Returns the output text."""
    settings = get_settings()
    ctx = RunContext(run_id)

    # Load workflow + the agents it references (then detach to snapshots).
    with SessionLocal() as db:
        workflow = db.get(Workflow, workflow_id)
        if workflow is None:
            raise ValueError("Workflow not found")
        agent_ids = {n["agent_id"] for n in (workflow.nodes or [])}
        agents = {
            a.id: a for a in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()
        }
        # Build the graph while the session is open (snapshots detach the data).
        graph = build_graph(workflow, agents, ctx)

    await event_bus.publish(
        Event(type="run_start", run_id=run_id, message="run started",
              data={"workflow_id": workflow_id, "input": input_text})
    )
    await ctx.record_message(MessageRole.human, input_text)

    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=input_text)],
             "last_output": "", "agent_outputs": {}},
            config={"recursion_limit": settings.max_graph_iterations},
        )
        output = result.get("last_output") or ""
        if not output and result.get("messages"):
            output = result["messages"][-1].content or ""
        await ctx.finalize(RunStatus.completed, output, None)
        return output
    except Exception as exc:  # noqa: BLE001
        await ctx.log("error", f"Run failed: {exc}", level="error")
        await ctx.finalize(RunStatus.failed, "", str(exc))
        raise


async def run_workflow(workflow_id: str, input_text: str, trigger: str = "ui") -> tuple[str, str]:
    """Convenience: create + execute a run. Returns (run_id, output_text)."""
    run_id = create_run(workflow_id, input_text, trigger)
    output = await execute_run(run_id, workflow_id, input_text)
    return run_id, output
