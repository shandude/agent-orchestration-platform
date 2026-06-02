"""Run context — the bridge between a live execution and persistence/monitoring.

A single `RunContext` is created per workflow run and threaded through every
agent node. It is the *one* place that:

* persists messages and log events to the database,
* publishes real-time events to the event bus (→ WebSocket), and
* accumulates token/cost totals for the run.

Keeping this in one object means agent nodes stay focused on reasoning, and we
never duplicate "save + broadcast + tally" logic.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import LogEvent, Message, MessageRole, Run, RunStatus
from app.runtime.events import Event, event_bus
from app.runtime.llm import Usage


class RunContext:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost_usd = 0.0

    # ── messages ────────────────────────────────────────────────────
    async def record_message(
        self,
        role: MessageRole,
        content: str,
        agent_id: str | None = None,
        agent_name: str | None = None,
        usage: Usage | None = None,
    ) -> None:
        usage = usage or Usage()
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.cost_usd = round(self.cost_usd + usage.cost_usd, 6)

        def _persist() -> None:
            with SessionLocal() as db:
                db.add(
                    Message(
                        run_id=self.run_id,
                        role=role,
                        agent_id=agent_id,
                        agent_name=agent_name,
                        content=content,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        cost_usd=usage.cost_usd,
                    )
                )
                db.commit()

        await asyncio.to_thread(_persist)

        await event_bus.publish(
            Event(
                type="message",
                run_id=self.run_id,
                message=content,
                data={
                    "role": role.value if isinstance(role, MessageRole) else role,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "cost_usd": usage.cost_usd,
                },
            )
        )
        if usage.cost_usd:
            await self._emit_cost()

    # ── logs ────────────────────────────────────────────────────────
    async def log(
        self,
        event_type: str,
        message: str = "",
        level: str = "info",
        data: dict | None = None,
    ) -> None:
        data = data or {}

        def _persist() -> None:
            with SessionLocal() as db:
                db.add(
                    LogEvent(
                        run_id=self.run_id,
                        level=level,
                        event_type=event_type,
                        message=message,
                        data=data,
                    )
                )
                db.commit()

        await asyncio.to_thread(_persist)
        await event_bus.publish(
            Event(
                type=event_type,
                run_id=self.run_id,
                level=level,
                message=message,
                data=data,
            )
        )

    async def _emit_cost(self) -> None:
        await event_bus.publish(
            Event(
                type="cost",
                run_id=self.run_id,
                message="cost update",
                data={
                    "total_prompt_tokens": self.prompt_tokens,
                    "total_completion_tokens": self.completion_tokens,
                    "total_cost_usd": self.cost_usd,
                },
            )
        )

    # ── run lifecycle ───────────────────────────────────────────────
    async def finalize(self, status: RunStatus, output_text: str, error: str | None) -> None:
        def _persist() -> None:
            with SessionLocal() as db:
                run = db.get(Run, self.run_id)
                if run is None:
                    return
                run.status = status
                run.output_text = output_text
                run.error = error
                run.total_prompt_tokens = self.prompt_tokens
                run.total_completion_tokens = self.completion_tokens
                run.total_cost_usd = self.cost_usd
                run.finished_at = datetime.now(timezone.utc)
                db.commit()

        await asyncio.to_thread(_persist)
        await event_bus.publish(
            Event(
                type="run_end",
                run_id=self.run_id,
                message=f"run {status.value}",
                data={
                    "status": status.value,
                    "output_text": output_text,
                    "error": error,
                    "total_cost_usd": self.cost_usd,
                    "total_prompt_tokens": self.prompt_tokens,
                    "total_completion_tokens": self.completion_tokens,
                },
            )
        )
