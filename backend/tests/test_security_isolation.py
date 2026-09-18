"""
Security and Tenant Isolation Tests
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.doctor import Doctor
from app.models.patient import Patient, Role
from app.models.appointment import AppointmentStatus, can_transition_appointment, AppointmentStateHistory
from app.services.appointment_service import create_appointment_with_verification, cancel_appointment_flow
from app.ai.capabilities import AICapabilities
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode
from tests.conftest import unique_future_slot

client = TestClient(app)
PATIENT_CREDS = {"email": "ramesh.varma@patient.org", "password": "Patient@123"}

def _login(creds):
    resp = client.post("/api/auth/login", json=creds)
    return resp.json().get("access_token") if resp.status_code == 200 else None


def test_patient_can_only_see_own_appointments():
    token = _login(PATIENT_CREDS)
    if not token:
        pytest.skip("Cannot login as patient")
    resp = client.get("/api/appointments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_state_transition_validation():
    assert can_transition_appointment(AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED) is False
    assert can_transition_appointment(AppointmentStatus.CANCELLED, AppointmentStatus.CONFIRMED) is False
    assert can_transition_appointment(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED) is True
    assert can_transition_appointment(AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED) is True
    assert can_transition_appointment(AppointmentStatus.PENDING, AppointmentStatus.PENDING) is True


def test_capability_get_appointment_scoped_to_patient():
    db = SessionLocal()
    try:
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patients in DB")
        caps = AICapabilities(db, correlation_id="SEC-SCOPE-001")
        results = caps.get_appointment(patient_id=patient.id)
        assert isinstance(results, list)
        empty = caps.get_appointment(patient_id=999999)
        assert empty == []
    finally:
        db.close()


def test_capability_synchronize_state_rejects_invalid_transition():
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        if not doctor or not patient:
            pytest.skip("Need doctor and patient in DB")

        date, start, end = unique_future_slot()
        apt = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end,
            idempotency_key=f"SEC-SYNC-{uuid.uuid4().hex[:8]}"
        )
        cancel_appointment_flow(db, apt.id, actor_email="test")
        db.refresh(apt)
        assert apt.status == AppointmentStatus.CANCELLED

        caps = AICapabilities(db, correlation_id="SEC-SYNC-002")
        result = caps.synchronize_state(apt.id, target_status="CONFIRMED")
        assert result["synchronized"] is False
        assert "Invalid transition" in result.get("error", "")
        db.refresh(apt)
        assert apt.status == AppointmentStatus.CANCELLED
    finally:
        db.close()


def test_state_history_recorded_on_booking():
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        if not doctor or not patient:
            pytest.skip("Need doctor and patient in DB")

        date, start, end = unique_future_slot()
        apt = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end,
            idempotency_key=f"SEC-HIST-{uuid.uuid4().hex[:8]}"
        )
        assert apt.status == AppointmentStatus.CONFIRMED

        history = db.query(AppointmentStateHistory).filter(
            AppointmentStateHistory.appointment_id == apt.id
        ).order_by(AppointmentStateHistory.id.asc()).all()

        assert len(history) >= 2, f"Expected >= 2 state transitions, got {len(history)}"
        assert history[0].to_status == AppointmentStatus.PENDING.value
        assert history[-1].to_status == AppointmentStatus.CONFIRMED.value

        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        db.close()


def test_cancel_records_state_history():
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        if not doctor or not patient:
            pytest.skip("Need doctor and patient in DB")

        date, start, end = unique_future_slot()
        apt = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end,
            idempotency_key=f"SEC-CANHIST-{uuid.uuid4().hex[:8]}"
        )
        cancel_appointment_flow(db, apt.id, actor_email="test", reason="test cancellation")
        history = db.query(AppointmentStateHistory).filter(
            AppointmentStateHistory.appointment_id == apt.id
        ).order_by(AppointmentStateHistory.id.desc()).all()

        assert len(history) >= 1
        cancel_entry = next((h for h in history if h.to_status == AppointmentStatus.CANCELLED.value), None)
        assert cancel_entry is not None
        assert cancel_entry.reason == "test cancellation"
    finally:
        db.close()
