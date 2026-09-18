"""
Appointment flow tests: idempotency, reschedule, cancel, state transitions.
"""
import uuid
import pytest
from app.database import SessionLocal
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentStatus
from app.services.appointment_service import (
    create_appointment_with_verification,
    cancel_appointment_flow,
    reschedule_appointment_flow
)
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode
from tests.conftest import unique_future_slot


def test_idempotent_booking_and_double_creation_prevention():
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        assert doctor and patient

        date, start, end = unique_future_slot()
        idempotency_key = f"TEST-IDEM-{uuid.uuid4().hex[:8]}"

        apt1 = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end,
            idempotency_key=idempotency_key
        )
        assert apt1.status == AppointmentStatus.CONFIRMED
        assert apt1.external_appointment_id is not None

        # Same idempotency key must return existing appointment
        apt2 = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end,
            idempotency_key=idempotency_key
        )
        assert apt1.id == apt2.id
        assert apt1.external_appointment_id == apt2.external_appointment_id

        cancel_appointment_flow(db, apt1.id, actor_email="test_cleaner")
    finally:
        db.close()


def test_reschedule_and_cancellation_flow():
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        date, start, end = unique_future_slot()

        apt = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end
        )
        assert apt.status == AppointmentStatus.CONFIRMED

        # Reschedule to a different unique slot on a far-future date
        date2, start2, end2 = unique_future_slot()
        rescheduled = reschedule_appointment_flow(
            db=db, appointment_id=apt.id,
            new_date=date2, new_start_time=start2, new_end_time=end2,
            actor_email="patient@test.com"
        )
        assert rescheduled.status == AppointmentStatus.RESCHEDULED
        assert rescheduled.start_time == start2

        cancelled = cancel_appointment_flow(
            db=db, appointment_id=apt.id,
            actor_email="patient@test.com", reason="Schedule conflict"
        )
        assert cancelled.status == AppointmentStatus.CANCELLED
    finally:
        db.close()


def test_state_transition_enforcement_prevents_double_cancel():
    """Cancelling an already-cancelled appointment returns it unchanged (idempotent)."""
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        date, start, end = unique_future_slot()

        apt = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end
        )
        cancel_appointment_flow(db, apt.id, actor_email="test")
        db.refresh(apt)
        assert apt.status == AppointmentStatus.CANCELLED

        # Cancel again — should be idempotent (return same CANCELLED appointment)
        again = cancel_appointment_flow(db, apt.id, actor_email="test")
        assert again.status == AppointmentStatus.CANCELLED
    finally:
        db.close()
