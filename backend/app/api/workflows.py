"""Workflow CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workflow
from app.schemas import WorkflowCreate, WorkflowOut, WorkflowUpdate

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowOut])
def list_workflows(db: Session = Depends(get_db)):
    return db.query(Workflow).order_by(Workflow.created_at).all()


@router.post("", response_model=WorkflowOut, status_code=201)
def create_workflow(payload: WorkflowCreate, db: Session = Depends(get_db)):
    wf = Workflow(**payload.model_dump())
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(workflow_id: str, payload: WorkflowUpdate, db: Session = Depends(get_db)):
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(wf, field, value)
    db.commit()
    db.refresh(wf)
    return wf


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, db: Session = Depends(get_db)):
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    db.delete(wf)
    db.commit()
