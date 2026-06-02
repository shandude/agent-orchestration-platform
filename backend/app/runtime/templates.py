"""Two pre-built workflow templates, seeded on first startup.

1. **Research → Write → Review** — demonstrates a *feedback loop*: the Editor
   either APPROVES (ends) or asks to REVISE (loops back to the Writer), bounded
   by the graph recursion limit.

2. **Customer Support Triage** — demonstrates *conditional branching*: a Triage
   agent classifies the request and routes to Technical or Billing. Its entry
   agent is bound to the Telegram channel, so a human can chat with it live.

Seeding is idempotent: agents/workflows are keyed by name and only created if
absent, so restarts never duplicate them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Agent, Workflow


def _get_or_create_agent(db: Session, name: str, **kwargs) -> Agent:
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        return existing
    agent = Agent(name=name, **kwargs)
    db.add(agent)
    db.flush()  # populate agent.id
    return agent


def _workflow_exists(db: Session, name: str) -> bool:
    return db.query(Workflow).filter(Workflow.name == name).first() is not None


def seed_templates(db: Session) -> None:
    # ── Template 1: Research → Write → Review (feedback loop) ─────────
    if not _workflow_exists(db, "Research & Review"):
        researcher = _get_or_create_agent(
            db, "Researcher",
            role="research analyst",
            system_prompt=(
                "Gather accurate, up-to-date facts on the user's topic using the "
                "web_search tool. Produce concise bullet-point findings with sources."
            ),
            model="gemini-2.0-flash",
            tools=["web_search", "http_get"],
            skills=["research", "fact-finding"],
            guardrails=["Never invent facts or sources."],
        )
        writer = _get_or_create_agent(
            db, "Writer",
            role="content writer",
            system_prompt=(
                "Using the researcher's findings (and any editor feedback in the "
                "transcript), write a clear, well-structured ~200-word summary for "
                "a general audience."
            ),
            model="gemini-2.0-flash",
            skills=["writing", "summarization"],
        )
        editor = _get_or_create_agent(
            db, "Editor",
            role="editor-in-chief",
            system_prompt=(
                "Review the Writer's latest draft for accuracy, clarity and "
                "completeness. If it needs changes, reply starting with the word "
                "REVISE followed by specific, actionable feedback. If it is good, "
                "reply starting with the word APPROVED followed by the final text."
            ),
            model="gemini-2.0-flash",
            temperature=0.0,
            skills=["editing", "quality-control"],
            guardrails=["Always begin your reply with either REVISE or APPROVED."],
        )
        db.add(
            Workflow(
                name="Research & Review",
                description=(
                    "Researcher gathers facts → Writer drafts a summary → Editor "
                    "reviews. Editor loops back to the Writer until APPROVED "
                    "(feedback loop)."
                ),
                is_template=True,
                entry_node="researcher",
                nodes=[
                    {"id": "researcher", "agent_id": researcher.id, "label": "Researcher",
                     "position": {"x": 80, "y": 160}},
                    {"id": "writer", "agent_id": writer.id, "label": "Writer",
                     "position": {"x": 380, "y": 160}},
                    {"id": "editor", "agent_id": editor.id, "label": "Editor",
                     "position": {"x": 680, "y": 160}},
                ],
                edges=[
                    {"source": "researcher", "target": "writer",
                     "condition": {"type": "always", "value": ""}},
                    {"source": "writer", "target": "editor",
                     "condition": {"type": "always", "value": ""}},
                    # Feedback loop: Editor → Writer only when it says REVISE.
                    {"source": "editor", "target": "writer",
                     "condition": {"type": "contains", "value": "REVISE"}},
                ],
            )
        )

    # ── Template 2: Customer Support Triage (branching + Telegram) ────
    if not _workflow_exists(db, "Customer Support Triage"):
        triage = _get_or_create_agent(
            db, "Triage Agent",
            role="support router",
            system_prompt=(
                "You are the first point of contact. Read the user's message and "
                "decide whether it is a TECHNICAL issue or a BILLING issue. Reply "
                "with one word only — TECHNICAL or BILLING — optionally followed by "
                "a one-line reason."
            ),
            model="gemini-2.0-flash",
            temperature=0.0,
            channels=["telegram"],          # ← reachable from Telegram
            skills=["classification", "routing"],
            guardrails=["Reply with exactly one of: TECHNICAL or BILLING."],
        )
        technical = _get_or_create_agent(
            db, "Technical Support",
            role="technical support specialist",
            system_prompt=(
                "Help the user resolve their technical problem with clear, friendly, "
                "step-by-step guidance. Use web_search if you need current details."
            ),
            model="gemini-2.0-flash",
            tools=["web_search"],
            skills=["troubleshooting"],
            guardrails=["Never ask for passwords or full card numbers."],
        )
        billing = _get_or_create_agent(
            db, "Billing Support",
            role="billing specialist",
            system_prompt=(
                "Help the user with billing, invoices, refunds and subscription "
                "questions in a clear, reassuring tone."
            ),
            model="gemini-2.0-flash",
            skills=["billing"],
            guardrails=["Never ask for full card numbers or CVV."],
        )
        db.add(
            Workflow(
                name="Customer Support Triage",
                description=(
                    "Triage agent classifies the request and routes to Technical "
                    "or Billing (conditional branching). Connected to Telegram."
                ),
                is_template=True,
                entry_node="triage",
                nodes=[
                    {"id": "triage", "agent_id": triage.id, "label": "Triage",
                     "position": {"x": 120, "y": 160}},
                    {"id": "technical", "agent_id": technical.id, "label": "Technical",
                     "position": {"x": 440, "y": 60}},
                    {"id": "billing", "agent_id": billing.id, "label": "Billing",
                     "position": {"x": 440, "y": 280}},
                ],
                edges=[
                    {"source": "triage", "target": "billing",
                     "condition": {"type": "contains", "value": "BILLING"}},
                    {"source": "triage", "target": "technical",
                     "condition": {"type": "contains", "value": "TECHNICAL"}},
                    # Default branch if classification is unclear.
                    {"source": "triage", "target": "technical",
                     "condition": {"type": "always", "value": ""}},
                ],
            )
        )

    db.commit()
