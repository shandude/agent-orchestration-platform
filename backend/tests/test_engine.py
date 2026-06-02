"""Agent runtime tests — workflow execution, message delivery, feedback loops.

These use the `fake_llm` fixture so they run fully offline and deterministically.
"""
from __future__ import annotations

from app.database import SessionLocal
from app.models import Agent, Message, MessageRole, Run, RunStatus, Workflow
from app.runtime.agent_node import build_system_prompt
from app.runtime.engine import create_run, execute_run


def _add_agent(db, name, system_prompt="", **kw) -> Agent:
    a = Agent(name=name, system_prompt=system_prompt, **kw)
    db.add(a)
    db.flush()
    return a


def test_build_system_prompt_includes_guardrails():
    prompt = build_system_prompt(
        {"name": "Doc", "role": "advisor", "guardrails": ["No medical advice"],
         "tools": ["web_search"]}
    )
    assert "Doc" in prompt
    assert "No medical advice" in prompt
    assert "web_search" in prompt


async def test_sequential_workflow_runs_and_persists_messages(fake_llm):
    with SessionLocal() as db:
        a = _add_agent(db, "Researcher")
        b = _add_agent(db, "Writer")
        wf = Workflow(
            name="seq", entry_node="n1",
            nodes=[{"id": "n1", "agent_id": a.id, "label": "Researcher"},
                   {"id": "n2", "agent_id": b.id, "label": "Writer"}],
            edges=[{"source": "n1", "target": "n2",
                    "condition": {"type": "always", "value": ""}}],
        )
        db.add(wf)
        db.commit()
        wf_id = wf.id

    run_id = create_run(wf_id, "research black holes", "test")
    output = await execute_run(run_id, wf_id, "research black holes")

    assert output  # Writer produced the final answer
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.completed
        roles = [m.role for m in db.query(Message).filter(Message.run_id == run_id).all()]
        # human input + both agents recorded => message delivery works
        assert MessageRole.human in roles
        assert roles.count(MessageRole.agent) >= 2
        assert run.total_cost_usd > 0  # token/cost tracking populated


async def test_feedback_loop_terminates(fake_llm):
    """Editor says REVISE once (loop back to Writer) then APPROVED (end)."""
    with SessionLocal() as db:
        writer = _add_agent(db, "Writer")
        editor = _add_agent(db, "Editor",
                            guardrails=["Always begin with REVISE or APPROVED"])
        wf = Workflow(
            name="loop", entry_node="w",
            nodes=[{"id": "w", "agent_id": writer.id, "label": "Writer"},
                   {"id": "e", "agent_id": editor.id, "label": "Editor"}],
            edges=[
                {"source": "w", "target": "e", "condition": {"type": "always", "value": ""}},
                {"source": "e", "target": "w", "condition": {"type": "contains", "value": "REVISE"}},
            ],
        )
        db.add(wf)
        db.commit()
        wf_id = wf.id

    run_id = create_run(wf_id, "write about the sea", "test")
    output = await execute_run(run_id, wf_id, "write about the sea")

    assert "APPROVED" in output
    # Editor was visited twice (REVISE then APPROVED) => the loop actually ran.
    assert fake_llm.calls.get("editor", 0) == 2
    with SessionLocal() as db:
        assert db.get(Run, run_id).status == RunStatus.completed
