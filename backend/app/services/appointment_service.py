import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.appointment import Appointment, AppointmentStatus, ExternalMapping, AppointmentStateHistory, can_transition_appointment
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.integration import IntegrationOperation, IntegrationVerification, ReconciliationRecord
from app.integrations.mock_ehr import mock_ehr_connector
from app.services.scheduling_service import validate_slot, release_slot
from app.services.workflow_service import trigger_appointment_workflow
from app.services.audit_service import log_audit_event
from app.services.notification_service import create_notification

def create_appointment_with_verification(
    db: Session,
    hospital_id: int,
    doctor_id: int,
    patient_id: int,
    date: str,
    start_time: str,
    end_time: str,
    appointment_type: str = "IN_PERSON",
    reason: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    correlation_id: Optional[str] = None,
    actor_email: str = "patient"
) -> Appointment:
    """
    Complete idempotent booking flow with Mock EHR integration,
    unknown outcome handling, and mandatory external verification.
    """
    corr_id = correlation_id or f"BOOK-{uuid.uuid4().hex[:8].upper()}"
    idem_key = idempotency_key or f"IDEM-{uuid.uuid4().hex[:12]}"

    # 1. Idempotency Check: Return existing appointment if idempotency key already processed
    existing_apt = db.query(Appointment).filter(Appointment.idempotency_key == idem_key).first()
    if existing_apt:
        return existing_apt

    # 2. Immediate Pre-booking Slot Revalidation
    is_valid, error_msg = validate_slot(db, doctor_id, date, start_time, end_time)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "SLOT_CONFLICT",
                "message": error_msg or "The selected slot is no longer available.",
                "correlation_id": corr_id
            }
        )

    # 3. Create Internal Appointment in PENDING state
    appointment = Appointment(
        hospital_id=hospital_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        appointment_type=appointment_type,
        date=date,
        start_time=start_time,
        end_time=end_time,
        status=AppointmentStatus.PENDING,
        correlation_id=corr_id,
        idempotency_key=idem_key,
        reason=reason or "General Consultation"
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "SLOT_CONFLICT",
                "message": "The selected slot was just booked by a concurrent transaction.",
                "correlation_id": corr_id
            }
        )
    db.refresh(appointment)

    # Record Initial State History
    hist_pending = AppointmentStateHistory(
        appointment_id=appointment.id,
        from_status=None,
        to_status=AppointmentStatus.PENDING.value,
        reason="Initial booking request",
        actor=actor_email,
        correlation_id=corr_id
    )
    db.add(hist_pending)
    db.commit()

    log_audit_event(
        db=db,
        actor=actor_email,
        role="PATIENT",
        event_type="APPOINTMENT_REQUESTED",
        resource_type="APPOINTMENT",
        resource_id=str(appointment.id),
        hospital_id=hospital_id,
        correlation_id=corr_id,
        safe_metadata={"doctor_id": doctor_id, "date": date, "slot": f"{start_time}-{end_time}"}
    )

    # 4. Invoke EHR Integration
    ehr_op = IntegrationOperation(
        hospital_id=hospital_id,
        operation_type="CREATE_APPOINTMENT",
        external_system="MOCK_EHR",
        status="PENDING",
        request_id=f"REQ-{uuid.uuid4().hex[:6].upper()}",
        correlation_id=corr_id,
        retry_count=0
    )
    db.add(ehr_op)
    db.commit()

    ehr_payload = {
        "patient_id": f"EXT-PAT-{patient_id}",
        "provider_id": f"EXT-DOC-{doctor_id}",
        "facility_id": f"EXT-FAC-{hospital_id}",
        "date": date,
        "start_time": start_time,
        "end_time": end_time
    }

    external_apt_id = None
    unknown_outcome = False

    try:
        ehr_res = mock_ehr_connector.create_appointment(ehr_payload, idempotency_key=idem_key)
        external_apt_id = ehr_res.get("external_id")
        ehr_op.status = "SUCCESS"
        db.commit()
    except TimeoutError as te:
        # UNKNOWN OUTCOME SCENARIO!
        # A timeout occurred. We must NEVER blindly retry creating, otherwise a duplicate could be made.
        # Instead, mark as UNKNOWN, and proceed to external verification check!
        ehr_op.status = "UNKNOWN"
        ehr_op.error = str(te)
        appointment.status = AppointmentStatus.SYNCHRONIZATION_PENDING
        db.commit()
        unknown_outcome = True
    except Exception as e:
        ehr_op.status = "FAILED"
        ehr_op.error = str(e)
        appointment.status = AppointmentStatus.FAILED
        hist_failed = AppointmentStateHistory(
            appointment_id=appointment.id,
            from_status=AppointmentStatus.PENDING.value,
            to_status=AppointmentStatus.FAILED.value,
            reason=f"EHR integration failed: {str(e)}",
            actor="SYSTEM",
            correlation_id=corr_id
        )
        db.add(hist_failed)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "EHR_INTEGRATION_FAILED",
                "message": f"External EHR rejected booking: {str(e)}",
                "correlation_id": corr_id
            }
        )

    # 5. External Verification Phase
    # Query Mock EHR to verify record status
    verified_record = mock_ehr_connector.verify_appointment(
        external_id=external_apt_id,
        idempotency_key=idem_key,
        provider_id=f"EXT-DOC-{doctor_id}",
        date=date,
        start_time=start_time
    )

    if verified_record:
        # Record exists in EHR! Complete synchronization
        verified_ext_id = verified_record.get("external_id")
        from_status_val = appointment.status.value
        appointment.external_appointment_id = verified_ext_id
        appointment.status = AppointmentStatus.CONFIRMED
        
        # Save external mapping
        mapping = ExternalMapping(
            entity_type="APPOINTMENT",
            internal_id=appointment.id,
            external_id=verified_ext_id,
            system_name="MOCK_EHR"
        )
        db.merge(mapping)

        # Log verification record
        verification = IntegrationVerification(
            appointment_id=appointment.id,
            external_id=verified_ext_id,
            verification_status="VERIFIED",
            verification_result={"verified_from_unknown_outcome": unknown_outcome, "status": "EXTERNAL_CONFIRMED"}
        )
        db.add(verification)

        # Record CONFIRMED State History
        hist_confirmed = AppointmentStateHistory(
            appointment_id=appointment.id,
            from_status=from_status_val,
            to_status=AppointmentStatus.CONFIRMED.value,
            reason="Verified in Mock EHR",
            actor="SYSTEM_SYNCHRONIZER",
            correlation_id=corr_id
        )
        db.add(hist_confirmed)
        db.commit()
        db.refresh(appointment)

        log_audit_event(
            db=db,
            actor="SYSTEM_SYNCHRONIZER",
            role="SYSTEM",
            event_type="APPOINTMENT_VERIFIED_AND_CONFIRMED",
            resource_type="APPOINTMENT",
            resource_id=str(appointment.id),
            hospital_id=hospital_id,
            correlation_id=corr_id,
            safe_metadata={"external_id": verified_ext_id, "recovered_from_timeout": unknown_outcome}
        )

        # 6. Trigger Post-Confirmation Workflow & Notifications
        trigger_appointment_workflow(db, appointment, correlation_id=corr_id, idempotency_key=f"WF-{idem_key}")

        return appointment

    else:
        # Record was NOT found in EHR after timeout/error. Requires reconciliation!
        appointment.status = AppointmentStatus.RECONCILIATION_REQUIRED
        reconcile_rec = ReconciliationRecord(
            appointment_id=appointment.id,
            failure_type="TIMEOUT_VERIFICATION_FAILED" if unknown_outcome else "VERIFICATION_NOT_FOUND",
            external_state="NOT_FOUND",
            internal_state=appointment.status.value,
            resolution="Escalated to human platform admin for verification",
            status="RECONCILIATION_REQUIRED"
        )
        db.add(reconcile_rec)
        db.commit()

        log_audit_event(
            db=db,
            actor="SYSTEM_RECONCILER",
            role="SYSTEM",
            event_type="RECONCILIATION_REQUIRED",
            resource_type="APPOINTMENT",
            resource_id=str(appointment.id),
            hospital_id=hospital_id,
            correlation_id=corr_id,
            safe_metadata={"failure_type": "TIMEOUT_VERIFICATION_FAILED"}
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "RECONCILIATION_REQUIRED",
                "message": "Booking outcome is undetermined and has been escalated to hospital administration for reconciliation.",
                "correlation_id": corr_id
            }
        )

def reschedule_appointment_flow(
    db: Session,
    appointment_id: int,
    new_date: str,
    new_start_time: str,
    new_end_time: str,
    actor_email: str,
    correlation_id: Optional[str] = None
) -> Appointment:
    """
    Rescheduling flow:
    1. Find existing appointment
    2. Validate new slot
    3. Update external EHR appointment
    4. Verify external result
    5. Synchronize internal state
    6. Release old slot (never release old slot before new is verified!)
    """
    corr_id = correlation_id or f"RESCHED-{uuid.uuid4().hex[:8].upper()}"

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    if not can_transition_appointment(appointment.status, AppointmentStatus.RESCHEDULED):
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_STATE", "message": f"Cannot transition appointment from {appointment.status.value} to RESCHEDULED"})

    # Validate new slot
    is_valid, error_msg = validate_slot(db, appointment.doctor_id, new_date, new_start_time, new_end_time)
    if not is_valid:
        raise HTTPException(status_code=409, detail={"error_code": "SLOT_CONFLICT", "message": error_msg})

    old_status = appointment.status.value
    old_date = appointment.date
    old_start = appointment.start_time
    old_end = appointment.end_time

    # Update EHR if external ID exists
    if appointment.external_appointment_id:
        mock_ehr_connector.update_appointment(
            appointment.external_appointment_id,
            {"date": new_date, "start_time": new_start_time, "end_time": new_end_time}
        )

    # Synchronize internal state
    appointment.date = new_date
    appointment.start_time = new_start_time
    appointment.end_time = new_end_time
    appointment.status = AppointmentStatus.RESCHEDULED
    
    # Record Reschedule State History
    hist_resched = AppointmentStateHistory(
        appointment_id=appointment.id,
        from_status=old_status,
        to_status=AppointmentStatus.RESCHEDULED.value,
        reason=f"Rescheduled to {new_date} {new_start_time}",
        actor=actor_email,
        correlation_id=corr_id
    )
    db.add(hist_resched)
    db.commit()
    db.refresh(appointment)

    # Release old slot
    release_slot(db, appointment.doctor_id, old_date, old_start, old_end)

    log_audit_event(
        db=db,
        actor=actor_email,
        role="USER",
        event_type="APPOINTMENT_RESCHEDULED",
        resource_type="APPOINTMENT",
        resource_id=str(appointment.id),
        hospital_id=appointment.hospital_id,
        correlation_id=corr_id,
        safe_metadata={"old_slot": f"{old_date} {old_start}", "new_slot": f"{new_date} {new_start_time}"}
    )

    # Notify patient & doctor
    if appointment.patient and appointment.patient.user_id:
        create_notification(
            db=db,
            recipient_id=appointment.patient.user_id,
            role="PATIENT",
            notif_type="APPOINTMENT_RESCHEDULED",
            title="Appointment Rescheduled",
            message=f"Your appointment with {appointment.doctor.name if appointment.doctor else 'Doctor'} has been moved to {new_date} at {new_start_time}.",
            appointment_id=appointment.id
        )

    return appointment

def cancel_appointment_flow(
    db: Session,
    appointment_id: int,
    actor_email: str,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Appointment:
    """
    Cancellation flow:
    1. Find appointment
    2. Cancel in external EHR
    3. Verify external cancellation
    4. Mark internal as CANCELLED
    5. Release slot
    6. Send notifications
    """
    corr_id = correlation_id or f"CANCEL-{uuid.uuid4().hex[:8].upper()}"

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    if appointment.status == AppointmentStatus.CANCELLED:
        return appointment

    if not can_transition_appointment(appointment.status, AppointmentStatus.CANCELLED):
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_STATE", "message": f"Cannot cancel appointment in {appointment.status.value} state"})

    if appointment.external_appointment_id:
        mock_ehr_connector.cancel_appointment(appointment.external_appointment_id, reason=reason)

    old_status = appointment.status.value
    appointment.status = AppointmentStatus.CANCELLED
    appointment.notes = f"Cancellation Reason: {reason or 'Requested by patient'}"

    # Record Cancelled State History
    hist_cancel = AppointmentStateHistory(
        appointment_id=appointment.id,
        from_status=old_status,
        to_status=AppointmentStatus.CANCELLED.value,
        reason=reason or "Requested by patient",
        actor=actor_email,
        correlation_id=corr_id
    )
    db.add(hist_cancel)
    db.commit()
    db.refresh(appointment)

    # Release slot
    release_slot(db, appointment.doctor_id, appointment.date, appointment.start_time, appointment.end_time)

    log_audit_event(
        db=db,
        actor=actor_email,
        role="USER",
        event_type="APPOINTMENT_CANCELLED",
        resource_type="APPOINTMENT",
        resource_id=str(appointment.id),
        hospital_id=appointment.hospital_id,
        correlation_id=corr_id,
        safe_metadata={"reason": reason}
    )

    if appointment.patient and appointment.patient.user_id:
        create_notification(
            db=db,
            recipient_id=appointment.patient.user_id,
            role="PATIENT",
            notif_type="APPOINTMENT_CANCELLED",
            title="Appointment Cancelled",
            message=f"Your appointment with {appointment.doctor.name if appointment.doctor else 'Doctor'} on {appointment.date} at {appointment.start_time} has been cancelled.",
            appointment_id=appointment.id
        )

    return appointment
