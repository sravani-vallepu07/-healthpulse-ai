from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workflow import Workflow, WorkflowExecution
from app.models.patient import User, Role
from app.auth.security import require_roles, verify_tenant_access

router = APIRouter(prefix="/workflows", tags=["Workflows"])

@router.get("")
def list_workflows(
    hospital_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    q = db.query(Workflow)
    if user.role == Role.HOSPITAL_ADMIN:
        q = q.filter(Workflow.hospital_id == user.hospital_id)
    elif hospital_id:
        q = q.filter(Workflow.hospital_id == hospital_id)
    return q.all()

@router.get("/executions")
def list_executions(
    appointment_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN, Role.DOCTOR]))
):
    q = db.query(WorkflowExecution)
    if appointment_id:
        q = q.filter(WorkflowExecution.appointment_id == appointment_id)
    executions = q.order_by(WorkflowExecution.id.desc()).limit(50).all()
    results = []
    for e in executions:
        results.append({
            "id": e.id,
            "workflow_id": e.workflow_id,
            "workflow_name": e.workflow.name if e.workflow else "Intake Workflow",
            "appointment_id": e.appointment_id,
            "status": e.status,
            "current_step": e.current_step,
            "execution_log": e.execution_log,
            "started_at": e.started_at,
            "completed_at": e.completed_at
        })
    return results
