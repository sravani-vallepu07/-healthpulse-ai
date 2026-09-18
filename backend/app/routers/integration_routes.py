from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.integration import IntegrationOperation
from app.models.patient import User, Role
from app.schemas.schemas import FailureModeUpdate, OperationOut, StandardResponse
from app.auth.security import require_roles
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode

router = APIRouter(prefix="/integrations", tags=["Integrations & Failure Simulator"])

@router.get("", response_model=List[OperationOut])
def list_operations(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    query = db.query(IntegrationOperation)
    if user.role == Role.HOSPITAL_ADMIN and user.hospital_id:
        query = query.filter((IntegrationOperation.hospital_id == user.hospital_id) | (IntegrationOperation.hospital_id.is_(None)))
    ops = query.order_by(IntegrationOperation.id.desc()).limit(50).all()
    return [OperationOut.model_validate(op) for op in ops]

@router.get("/failure-mode")
def get_failure_mode(user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))):
    return {
        "current_failure_mode": mock_ehr_connector.get_failure_mode().value,
        "available_modes": [m.value for m in FailureMode],
        "description": "Platform Admins can trigger TIMEOUT to evaluate the Unknown Outcome and Verification Recovery Flow."
    }

@router.post("/failure-mode")
def set_failure_mode(
    payload: FailureModeUpdate,
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN]))
):
    try:
        mode = FailureMode(payload.failure_mode)
        mock_ehr_connector.set_failure_mode(mode, delay_seconds=payload.delay_seconds)
        return {
            "success": True,
            "message": f"Mock EHR failure mode set to {mode.value}",
            "delay_seconds": payload.delay_seconds
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_MODE", "message": f"Invalid mode. Choose from {[m.value for m in FailureMode]}"}
        )

@router.post("/test")
def test_ehr_connection(user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))):
    facility = mock_ehr_connector.lookup_facility("EXT-FAC-001")
    return {
        "status": "HEALTHY",
        "system": "MOCK_EHR",
        "sample_facility": facility,
        "current_failure_mode": mock_ehr_connector.get_failure_mode().value
    }
