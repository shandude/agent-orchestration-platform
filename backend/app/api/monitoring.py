"""Live monitoring WebSocket + platform meta endpoints.

The frontend opens one WebSocket to `/ws/monitor` and receives every runtime
event (node start/end, tool calls, messages, token/cost updates, run end) in
real time. This is the "live monitoring with real-time logs, inter-agent
messages and token/cost tracking" requirement.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.runtime.events import event_bus

router = APIRouter(tags=["monitoring"])


@router.get("/api/meta")
def meta():
    """Surface platform status to the UI (e.g. whether channels are live)."""
    settings = get_settings()
    return {
        "llm_enabled": settings.llm_enabled,
        "telegram_enabled": settings.telegram_enabled,
        "default_model": settings.default_model,
        "max_graph_iterations": settings.max_graph_iterations,
    }


@router.websocket("/ws/monitor")
async def monitor_ws(websocket: WebSocket):
    await websocket.accept()
    async with event_bus.subscribe() as queue:
        try:
            # Greet so the client knows the stream is live.
            await websocket.send_json({"type": "connected", "message": "monitor stream open"})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    await websocket.send_json(event.to_dict())
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxies from closing an idle socket.
                    await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001 — never let one socket take down others
            pass
