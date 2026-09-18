from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.doctor import Doctor, Calendar, Availability, AvailabilityStatus, BlockedSlot
from app.models.patient import User, Role
from app.schemas.schemas import SlotQuery, SlotOut, AvailabilityCreate, BlockedSlotCreate, StandardResponse
from app.auth.security import require_current_user, require_roles, verify_tenant_access
from app.services.scheduling_service import get_available_slots, validate_slot

router = APIRouter(prefix="/availability", tags=["Availability & Scheduling"])

@router.get("", response_model=List[SlotOut])
def get_slots(
    doctor_id: Optional[int] = None,
    hospital_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    slots = get_available_slots(
        db=db,
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        specialty_id=specialty_id,
        date=date
    )
    return slots

@router.post("/check")
def check_slot(
    doctor_id: int,
    date: str,
    start_time: str,
    end_time: str,
    db: Session = Depends(get_db)
):
    valid, msg = validate_slot(db, doctor_id, date, start_time, end_time)
    return {
        "is_available": valid,
        "message": msg or "Slot is open and available for booking"
    }

@router.post("")
def add_availability(
    payload: AvailabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN, Role.DOCTOR]))
):
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Doctor not found"})

    verify_tenant_access(user, doctor.hospital_id)

    avail = Availability(
        doctor_id=payload.doctor_id,
        calendar_id=payload.calendar_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=AvailabilityStatus.AVAILABLE
    )
    db.add(avail)
    db.commit()
    return {"success": True, "message": "Availability window added"}

@router.post("/blocked")
def block_slot(
    payload: BlockedSlotCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN, Role.DOCTOR]))
):
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Doctor not found"})

    verify_tenant_access(user, doctor.hospital_id)

    blocked = BlockedSlot(
        doctor_id=payload.doctor_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        reason=payload.reason
    )
    db.add(blocked)
    db.commit()
    return {"success": True, "message": "Slot blocked successfully"}
