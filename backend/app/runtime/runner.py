"""Fire-and-forget run launcher.

Both the REST API and the Telegram channel need to start a workflow run without
blocking the caller (the UI subscribes to the WebSocket to watch progress; the
Telegram handler awaits the result to reply). This module centralises launching
and keeps strong references to in-flight tasks so they are not garbage-collected
mid-run.
"""
from __future__ import annotations

import asyncio

from app.runtime.engine import create_run, execute_run

_background_tasks: set[asyncio.Task] = set()


def launch_run(workflow_id: str, input_text: str, trigger: str = "ui") -> str:
    """Create a run row and execute it in the background. Returns the run id."""
    run_id = create_run(workflow_id, input_text, trigger)
    task = asyncio.create_task(_safe_execute(run_id, workflow_id, input_text))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return run_id


async def _safe_execute(run_id: str, workflow_id: str, input_text: str) -> None:
    try:
        await execute_run(run_id, workflow_id, input_text)
    except Exception:  # noqa: BLE001 — already recorded on the run; just swallow.
        pass
