"""Pydantic schemas — the API request/response contracts.

Kept separate from the ORM models so the wire format can evolve independently
of the database layout, and so we never accidentally leak internal fields.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── Agents ──────────────────────────────────────────────────────────
class AgentBase(BaseModel):
    name: str
    role: str = ""
    system_prompt: str = ""
    model: str = "gemini-2.5-flash"
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    interaction_rules: str = ""
    schedule: dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.3
    max_tokens: int = 1024
    memory_enabled: bool = True
    memory_window: int = 10


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[list[str]] = None
    channels: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    guardrails: Optional[list[str]] = None
    interaction_rules: Optional[str] = None
    schedule: Optional[dict[str, Any]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    memory_enabled: Optional[bool] = None
    memory_window: Optional[int] = None


class AgentOut(AgentBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Workflows ───────────────────────────────────────────────────────
class EdgeCondition(BaseModel):
    # `always`   -> unconditional edge
    # `contains` -> follow if last output contains `value` (case-insensitive)
    # `llm`      -> a small router LLM decides between outgoing edges
    type: Literal["always", "contains", "llm"] = "always"
    value: str = ""


class WorkflowNode(BaseModel):
    id: str
    agent_id: str
    label: str = ""
    # Free-form canvas position so the visual builder can round-trip layout.
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: EdgeCondition = Field(default_factory=EdgeCondition)


class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entry_node: Optional[str] = None


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[list[WorkflowNode]] = None
    edges: Optional[list[WorkflowEdge]] = None
    entry_node: Optional[str] = None


class WorkflowOut(WorkflowBase):
    id: str
    is_template: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Runs / messages / logs ──────────────────────────────────────────
class RunRequest(BaseModel):
    input_text: str
    trigger: str = "ui"


class MessageOut(BaseModel):
    id: str
    run_id: Optional[str]
    role: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    content: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger: str
    input_text: str
    output_text: str
    error: Optional[str]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    created_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class RunDetail(RunOut):
    messages: list[MessageOut] = Field(default_factory=list)


class LogEventOut(BaseModel):
    id: str
    run_id: Optional[str]
    level: str
    event_type: str
    message: str
    data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
