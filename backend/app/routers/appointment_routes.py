from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import User, Patient, Role
from app.schemas.schemas import (
    AppointmentCreate, AppointmentReschedule, AppointmentCancel, 
    AppointmentOut, StandardResponse
)
from app.auth.security import require_current_user, require_roles, verify_tenant_access
from app.services.appointment_service import (
    create_appointment_with_verification,
    reschedule_appointment_flow,
    cancel_appointment_flow
)
from app.integrations.mock_ehr import mock_ehr_connector

router = APIRouter(prefix="/appointments", tags=["Appointments"])

@router.post("", response_model=AppointmentOut)
def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    patient_id = payload.patient_id
    if user.role == Role.PATIENT:
        if not user.patient_profile:
            raise HTTPException(status_code=400, detail={"error_code": "NO_PROFILE", "message": "Patient profile not found"})
        patient_id = user.patient_profile.id
    elif not patient_id:
        raise HTTPException(status_code=400, detail={"error_code": "MISSING_PATIENT", "message": "patient_id required"})

    appointment = create_appointment_with_verification(
        db=db,
        hospital_id=payload.hospital_id,
        doctor_id=payload.doctor_id,
        patient_id=patient_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        appointment_type=payload.appointment_type,
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
        correlation_id=payload.correlation_id,
        actor_email=user.email
    )

    out = AppointmentOut.model_validate(appointment)
    out.hospital_name = appointment.hospital.name if appointment.hospital else None
    out.doctor_name = appointment.doctor.name if appointment.doctor else None
    out.specialty = appointment.doctor.specialty.name if appointment.doctor and appointment.doctor.specialty else None
    out.patient_name = appointment.patient.name if appointment.patient else None
    return out

@router.get("", response_model=List[AppointmentOut])
def list_appointments(
    hospital_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    q = db.query(Appointment)

    # Role & Tenant Isolation Rules:
    if user.role == Role.PATIENT:
        if not user.patient_profile:
            return []
        q = q.filter(Appointment.patient_id == user.patient_profile.id)
    elif user.role == Role.DOCTOR:
        if not user.doctor_profile:
            return []
        q = q.filter(Appointment.doctor_id == user.doctor_profile.id)
    elif user.role == Role.HOSPITAL_ADMIN:
        q = q.filter(Appointment.hospital_id == user.hospital_id)
    else: # PLATFORM_ADMIN
        if hospital_id:
            q = q.filter(Appointment.hospital_id == hospital_id)

    if doctor_id and user.role != Role.DOCTOR:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if patient_id and user.role != Role.PATIENT:
        q = q.filter(Appointment.patient_id == patient_id)
    if status_filter:
        q = q.filter(Appointment.status == status_filter)

    appointments = q.order_by(Appointment.id.desc()).all()
    results = []
    for a in appointments:
        out = AppointmentOut.model_validate(a)
        out.hospital_name = a.hospital.name if a.hospital else None
        out.doctor_name = a.doctor.name if a.doctor else None
        out.specialty = a.doctor.specialty.name if a.doctor and a.doctor.specialty else None
        out.patient_name = a.patient.name if a.patient else None
        results.append(out)
    return results

@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    # Check access
    if user.role == Role.PATIENT and (not user.patient_profile or apt.patient_id != user.patient_profile.id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})
    elif user.role == Role.DOCTOR and (not user.doctor_profile or apt.doctor_id != user.doctor_profile.id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})
    elif user.role == Role.HOSPITAL_ADMIN:
        verify_tenant_access(user, apt.hospital_id)

    out = AppointmentOut.model_validate(apt)
    out.hospital_name = apt.hospital.name if apt.hospital else None
    out.doctor_name = apt.doctor.name if apt.doctor else None
    out.specialty = apt.doctor.specialty.name if apt.doctor and apt.doctor.specialty else None
    out.patient_name = apt.patient.name if apt.patient else None
    return out

@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    existing = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    if user.role == Role.PATIENT and (not user.patient_profile or existing.patient_id != user.patient_profile.id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})
    elif user.role == Role.HOSPITAL_ADMIN:
        verify_tenant_access(user, existing.hospital_id)

    apt = reschedule_appointment_flow(
        db=db,
        appointment_id=appointment_id,
        new_date=payload.date,
        new_start_time=payload.start_time,
        new_end_time=payload.end_time,
        actor_email=user.email,
        correlation_id=payload.correlation_id
    )
    out = AppointmentOut.model_validate(apt)
    out.hospital_name = apt.hospital.name if apt.hospital else None
    out.doctor_name = apt.doctor.name if apt.doctor else None
    out.specialty = apt.doctor.specialty.name if apt.doctor and apt.doctor.specialty else None
    out.patient_name = apt.patient.name if apt.patient else None
    return out

@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentCancel,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    existing = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    if user.role == Role.PATIENT and (not user.patient_profile or existing.patient_id != user.patient_profile.id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})
    elif user.role == Role.HOSPITAL_ADMIN:
        verify_tenant_access(user, existing.hospital_id)

    apt = cancel_appointment_flow(
        db=db,
        appointment_id=appointment_id,
        actor_email=user.email,
        reason=payload.reason,
        correlation_id=payload.correlation_id
    )
    out = AppointmentOut.model_validate(apt)
    out.hospital_name = apt.hospital.name if apt.hospital else None
    out.doctor_name = apt.doctor.name if apt.doctor else None
    out.specialty = apt.doctor.specialty.name if apt.doctor and apt.doctor.specialty else None
    out.patient_name = apt.patient.name if apt.patient else None
    return out

@router.post("/{appointment_id}/verify")
def verify_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    if user.role == Role.PATIENT and (not user.patient_profile or apt.patient_id != user.patient_profile.id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})
    elif user.role == Role.HOSPITAL_ADMIN:
        verify_tenant_access(user, apt.hospital_id)

    record = mock_ehr_connector.verify_appointment(
        external_id=apt.external_appointment_id,
        idempotency_key=apt.idempotency_key
    )

    return {
        "appointment_id": apt.id,
        "internal_status": apt.status.value,
        "is_verified_in_ehr": record is not None,
        "external_record": record
    }
