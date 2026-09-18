from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.tenant import Hospital
from app.models.doctor import Doctor
from app.models.patient import User, Role
from app.models.integration import IntegrationOperation, IntegrationVerification, ReconciliationRecord
from app.models.ai import CapabilityExecution
from app.auth.security import require_roles

router = APIRouter(prefix="/ops", tags=["Operational Overview & Reconciliation"])

@router.get("/overview")
def get_operational_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    hospitals_count = db.query(Hospital).count()
    doctors_count = db.query(Doctor).count()
    appointments_count = db.query(Appointment).count()
    reconciliation_count = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "RECONCILIATION_REQUIRED").count()
    capabilities_count = db.query(CapabilityExecution).count()

    recent_appointments = db.query(Appointment).order_by(Appointment.id.desc()).limit(10).all()
    recent_list = []
    for a in recent_appointments:
        recent_list.append({
            "id": a.id,
            "correlation_id": a.correlation_id,
            "hospital": a.hospital.name if a.hospital else "Hospital",
            "doctor": a.doctor.name if a.doctor else "Doctor",
            "patient": a.patient.name if a.patient else "Patient",
            "date": a.date,
            "time": a.start_time,
            "status": a.status.value,
            "external_id": a.external_appointment_id
        })

    return {
        "metrics": {
            "hospitals": hospitals_count,
            "doctors": doctors_count,
            "appointments": appointments_count,
            "pending_reconciliations": reconciliation_count,
            "capability_executions": capabilities_count
        },
        "recent_bookings": recent_list
    }

@router.get("/reconciliation")
def list_reconciliations(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    records = db.query(ReconciliationRecord).order_by(ReconciliationRecord.id.desc()).all()
    results = []
    for r in records:
        results.append({
            "id": r.id,
            "appointment_id": r.appointment_id,
            "failure_type": r.failure_type,
            "external_state": r.external_state,
            "internal_state": r.internal_state,
            "resolution": r.resolution,
            "status": r.status,
            "created_at": r.created_at
        })
    return results

@router.post("/reconciliation/{record_id}/resolve")
def resolve_reconciliation(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN]))
):
    rec = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliation record not found")
    rec.status = "RESOLVED"
    rec.resolution = f"Manually reconciled by Platform Admin {user.email}"
    db.commit()
    return {"success": True, "message": "Reconciliation resolved"}
