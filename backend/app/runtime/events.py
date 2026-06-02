"""In-process async event bus for live monitoring.

The runtime emits structured events (node started, tool called, message
produced, token/cost update, run finished). Subscribers — chiefly the
monitoring WebSocket — receive them in real time via per-subscriber asyncio
queues. This decouples the runtime from any particular transport: the engine
just calls `event_bus.publish(...)` and never knows who is listening.

It is intentionally in-process (single-node). For a multi-node deployment this
is the seam where you would swap in Redis pub/sub or NATS — noted in the README
"future improvements".
"""
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    """A single monitoring event."""

    type: str                      # node_start | node_end | tool_call | message | cost | run_start | run_end | error
    run_id: str | None = None
    level: str = "info"            # info | warn | error
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    """Fan-out broadcaster backed by per-subscriber queues."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        """Deliver an event to every current subscriber (non-blocking)."""
        async with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            # Never let a slow/full consumer block the runtime.
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Event]]:
        """Context manager yielding a queue that receives all future events."""
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers.add(q)
        try:
            yield q
        finally:
            async with self._lock:
                self._subscribers.discard(q)


# Module-level singleton shared across the app.
event_bus = EventBus()
