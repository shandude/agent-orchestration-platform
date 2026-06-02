"""Run execution + history endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import LogEvent, Message, Run, Workflow
from app.runtime.runner import launch_run
from app.schemas import LogEventOut, MessageOut, RunDetail, RunOut, RunRequest

router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/workflows/{workflow_id}/run", response_model=RunOut, status_code=202)
def run_workflow_endpoint(
    workflow_id: str, payload: RunRequest, db: Session = Depends(get_db)
):
    if not get_settings().llm_enabled:
        raise HTTPException(400, "GOOGLE_API_KEY is not configured on the server.")
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    if not (wf.nodes or []):
        raise HTTPException(400, "Workflow has no nodes to run.")

    run_id = launch_run(workflow_id, payload.input_text, payload.trigger)
    return db.get(Run, run_id)


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), limit: int = 50):
    return db.query(Run).order_by(Run.created_at.desc()).limit(limit).all()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    messages = (
        db.query(Message)
        .filter(Message.run_id == run_id)
        .order_by(Message.created_at)
        .all()
    )
    detail = RunDetail.model_validate(run)
    detail.messages = [MessageOut.model_validate(m) for m in messages]
    return detail


@router.get("/runs/{run_id}/logs", response_model=list[LogEventOut])
def get_run_logs(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(LogEvent)
        .filter(LogEvent.run_id == run_id)
        .order_by(LogEvent.created_at)
        .all()
    )
