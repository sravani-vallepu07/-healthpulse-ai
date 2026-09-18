from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import Hospital, HospitalStatus
from app.models.doctor import Doctor, DoctorStatus, Calendar
from app.models.patient import User, Role
from app.schemas.schemas import DoctorCreate, DoctorUpdate, DoctorOut
from app.auth.security import require_current_user, require_roles, verify_tenant_access
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/doctors", tags=["Doctors"])

@router.post("", response_model=DoctorOut)
def create_doctor(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    verify_tenant_access(user, payload.hospital_id)

    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Hospital not found"})

    # Check if hospital is approved
    if hospital.status != HospitalStatus.APPROVED and user.role != Role.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "HOSPITAL_NOT_APPROVED", "message": "Cannot add active doctors to an unapproved hospital"}
        )

    doctor = Doctor(
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
        specialty_id=payload.specialty_id,
        name=payload.name,
        qualifications=payload.qualifications,
        experience=payload.experience,
        languages=payload.languages,
        consultation_types=payload.consultation_types,
        appointment_duration=payload.appointment_duration,
        status=payload.status,
        external_provider_id=f"EXT-DOC-{payload.hospital_id}-{payload.name.replace(' ', '')}"
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    # Automatically initialize primary calendar for doctor
    calendar = Calendar(doctor_id=doctor.id, name="Standard Clinic Schedule", active=True)
    db.add(calendar)
    db.commit()

    log_audit_event(
        db=db,
        actor=user.email,
        role=user.role.value,
        event_type="DOCTOR_CREATED",
        resource_type="DOCTOR",
        resource_id=str(doctor.id),
        hospital_id=doctor.hospital_id,
        correlation_id=f"DOC-{doctor.id}"
    )

    out = DoctorOut.model_validate(doctor)
    out.hospital_name = hospital.name
    if doctor.specialty:
        out.specialty_name = doctor.specialty.name
    return out

@router.get("", response_model=List[DoctorOut])
def list_doctors(
    hospital_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Doctor)
    if hospital_id:
        q = q.filter(Doctor.hospital_id == hospital_id)
    if specialty_id:
        q = q.filter(Doctor.specialty_id == specialty_id)
    if status_filter:
        q = q.filter(Doctor.status == status_filter)

    doctors = q.all()
    results = []
    for d in doctors:
        item = DoctorOut.model_validate(d)
        item.hospital_name = d.hospital.name if d.hospital else None
        item.specialty_name = d.specialty.name if d.specialty else None
        results.append(item)
    return results

@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Doctor not found"})
    out = DoctorOut.model_validate(doctor)
    out.hospital_name = doctor.hospital.name if doctor.hospital else None
    out.specialty_name = doctor.specialty.name if doctor.specialty else None
    return out

@router.put("/{doctor_id}", response_model=DoctorOut)
def update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Doctor not found"})

    # Doctor can edit themselves; hospital admin can edit doctor in their hospital
    if user.role == Role.DOCTOR and doctor.user_id != user.id:
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "You can only update your own doctor profile"})
    elif user.role == Role.HOSPITAL_ADMIN:
        verify_tenant_access(user, doctor.hospital_id)

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(doctor, field, value)

    db.commit()
    db.refresh(doctor)

    out = DoctorOut.model_validate(doctor)
    out.hospital_name = doctor.hospital.name if doctor.hospital else None
    out.specialty_name = doctor.specialty.name if doctor.specialty else None
    return out
