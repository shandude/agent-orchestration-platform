"""ORM models — the persistence layer.

Five entities model the whole platform:

* Agent     — a configurable AI worker (personality, tools, guardrails, ...).
* Workflow  — a graph of agent-nodes + edges (conditions / feedback loops).
* Run       — one execution of a workflow (status, cost, timing).
* Message   — every message produced (human, agent, inter-agent, tool, system).
* LogEvent  — fine-grained monitoring events (node started, tool called, ...).

JSON columns are used for the flexible, user-configurable bits (tool lists,
graph topology, guardrails) so agents/workflows stay schema-light and the UI
can evolve configurable dimensions without migrations.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class MessageRole(str, enum.Enum):
    human = "human"          # from a person (UI or Telegram)
    agent = "agent"          # an agent's response
    tool = "tool"            # a tool's output
    system = "system"        # framework/system note
    inter_agent = "inter_agent"  # one agent handing off to another


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String, default="gemini-2.5-flash")

    # Configurable dimensions (stored as JSON for flexibility).
    tools: Mapped[list] = mapped_column(JSON, default=list)        # ["web_search", ...]
    channels: Mapped[list] = mapped_column(JSON, default=list)     # ["telegram"]
    skills: Mapped[list] = mapped_column(JSON, default=list)       # freeform tags
    guardrails: Mapped[list] = mapped_column(JSON, default=list)   # ["no medical advice"]
    interaction_rules: Mapped[str] = mapped_column(Text, default="")
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)     # {"cron": "..."} (optional)

    # Limits / memory configuration.
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    memory_enabled: Mapped[bool] = mapped_column(default=True)
    memory_window: Mapped[int] = mapped_column(Integer, default=10)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_template: Mapped[bool] = mapped_column(default=False)

    # Graph topology. nodes: [{id, agent_id, label}], edges:
    # [{source, target, condition: {type, value}}]. entry: node id.
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    edges: Mapped[list] = mapped_column(JSON, default=list)
    entry_node: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    runs: Mapped[list["Run"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE")
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.pending
    )
    trigger: Mapped[str] = mapped_column(String, default="ui")  # ui | telegram | api
    input_text: Mapped[str] = mapped_column(Text, default="")
    output_text: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Aggregated cost/usage across all LLM calls in the run.
    total_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="runs")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")

    # Per-message usage (only set on agent messages that hit the LLM).
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped["Run | None"] = relationship(back_populates="messages")


class LogEvent(Base):
    __tablename__ = "log_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    level: Mapped[str] = mapped_column(String, default="info")  # info|warn|error
    event_type: Mapped[str] = mapped_column(String)  # node_start|tool_call|...
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
