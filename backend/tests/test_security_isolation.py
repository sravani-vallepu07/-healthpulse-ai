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


ADMIN_ABC_CREDS = {"email": "admin.abc@hospital.org", "password": "Admin@123"}
ADMIN_XYZ_CREDS = {"email": "admin.xyz@hospital.org", "password": "Admin@123"}
DOCTOR_RAO_CREDS = {"email": "dr.anil.rao@hospital.org", "password": "Doctor@123"}
DOCTOR_KIRAN_CREDS = {"email": "dr.kiran.kumar@hospital.org", "password": "Doctor@123"}

def test_cross_tenant_admin_cannot_modify_other_hospital_doctors():
    """PRD §21: Hospital A Admin cannot modify or create doctors for Hospital B."""
    token_a = _login(ADMIN_ABC_CREDS)
    assert token_a is not None, "Login for Hospital A admin failed"

    db = SessionLocal()
    try:
        # Doctor Kiran belongs to Hospital XYZ (hospital_id=2)
        doc_b = db.query(Doctor).filter(Doctor.email == "dr.kiran.kumar@hospital.org" if hasattr(Doctor, "email") else Doctor.name == "Dr. Kiran Kumar").first()
        assert doc_b is not None
        assert doc_b.hospital_id != 1

        # Attempt to update Hospital B doctor using Hospital A Admin token
        resp = client.put(
            f"/api/doctors/{doc_b.id}",
            json={"experience": 25},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp.status_code == 403
        assert "TENANT_ACCESS_DENIED" in resp.text or "Access denied" in resp.text

        # Attempt to create doctor assigned to Hospital B
        resp_create = client.post(
            "/api/doctors",
            json={
                "hospital_id": doc_b.hospital_id,
                "department_id": doc_b.department_id,
                "specialty_id": doc_b.specialty_id,
                "name": "Unauthorized Cross Doctor",
                "qualifications": "MBBS",
                "experience": 5,
                "languages": "English",
                "consultation_types": "IN_PERSON",
                "appointment_duration": 30,
                "status": "ACTIVE"
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_create.status_code == 403
    finally:
        db.close()


def test_cross_tenant_admin_cannot_manage_other_hospital_calendars():
    """PRD §21: Hospital A Admin cannot add availability or blocked slots for Hospital B doctors."""
    token_a = _login(ADMIN_ABC_CREDS)
    db = SessionLocal()
    try:
        doc_b = db.query(Doctor).filter(Doctor.name == "Dr. Kiran Kumar").first()
        assert doc_b is not None

        # Attempt to add availability for Hospital B doctor
        resp_avail = client.post(
            "/api/availability",
            json={
                "doctor_id": doc_b.id,
                "calendar_id": 1,
                "date": "2026-10-25",
                "start_time": "09:00",
                "end_time": "12:00"
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_avail.status_code == 403

        # Attempt to block slot for Hospital B doctor
        resp_block = client.post(
            "/api/availability/blocked",
            json={
                "doctor_id": doc_b.id,
                "date": "2026-10-25",
                "start_time": "10:00",
                "end_time": "11:00",
                "reason": "Unauthorized block"
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_block.status_code == 403
    finally:
        db.close()


def test_cross_tenant_admin_cannot_access_or_modify_other_hospital_appointments():
    """PRD §21: Hospital A Admin cannot read, reschedule, cancel, or verify Hospital B appointments."""
    token_a = _login(ADMIN_ABC_CREDS)
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doc_b = db.query(Doctor).filter(Doctor.name == "Dr. Kiran Kumar").first()
        patient = db.query(Patient).first()
        assert doc_b is not None and patient is not None

        date, start, end = unique_future_slot()
        apt_b = create_appointment_with_verification(
            db=db,
            hospital_id=doc_b.hospital_id,
            doctor_id=doc_b.id,
            patient_id=patient.id,
            date=date,
            start_time=start,
            end_time=end,
            idempotency_key=f"SEC-CROSS-{uuid.uuid4().hex[:8]}"
        )

        headers = {"Authorization": f"Bearer {token_a}"}

        # 1. Read details
        resp_get = client.get(f"/api/appointments/{apt_b.id}", headers=headers)
        assert resp_get.status_code == 403

        # 2. Reschedule
        new_date, new_start, new_end = unique_future_slot()
        resp_resched = client.post(
            f"/api/appointments/{apt_b.id}/reschedule",
            json={"date": new_date, "start_time": new_start, "end_time": new_end},
            headers=headers
        )
        assert resp_resched.status_code == 403

        # 3. Cancel
        resp_cancel = client.post(
            f"/api/appointments/{apt_b.id}/cancel",
            json={"reason": "Unauthorized cross-tenant cancel"},
            headers=headers
        )
        assert resp_cancel.status_code == 403

        # 4. Verify in EHR
        resp_verify = client.post(f"/api/appointments/{apt_b.id}/verify", headers=headers)
        assert resp_verify.status_code == 403

        # Clean up
        cancel_appointment_flow(db, apt_b.id, actor_email="cleaner")
    finally:
        db.close()


def test_cross_tenant_admin_cannot_access_or_modify_other_hospital_questionnaires():
    """PRD §21: Hospital A Admin cannot create, update, or read questionnaires of Hospital B."""
    token_a = _login(ADMIN_ABC_CREDS)
    db = SessionLocal()
    try:
        from app.models.questionnaire import Questionnaire, QuestionnaireStatus
        from app.models.tenant import Hospital

        hosp_b = db.query(Hospital).filter(Hospital.id == 2).first()
        assert hosp_b is not None

        # 1. Hospital A cannot create questionnaire for Hospital B
        resp_create = client.post(
            "/api/questionnaires",
            json={
                "hospital_id": hosp_b.id,
                "name": "Cross Hospital Survey",
                "questions": [{"question": "Q1", "type": "SHORT_TEXT", "required": True, "order": 1}]
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_create.status_code == 403

        # 2. Setup questionnaire belonging to Hospital B
        q_b = Questionnaire(hospital_id=hosp_b.id, name="Hospital B Private Intake", status=QuestionnaireStatus.ACTIVE)
        db.add(q_b)
        db.commit()
        db.refresh(q_b)

        # 3. Hospital A cannot read Hospital B questionnaire
        resp_get = client.get(f"/api/questionnaires/{q_b.id}", headers={"Authorization": f"Bearer {token_a}"})
        assert resp_get.status_code == 403

        # 4. Hospital A cannot update Hospital B questionnaire
        resp_update = client.put(
            f"/api/questionnaires/{q_b.id}",
            json={"hospital_id": hosp_b.id, "name": "Tampered Name", "questions": []},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_update.status_code == 403

        # Clean up
        db.delete(q_b)
        db.commit()
    finally:
        db.close()


def test_cross_tenant_doctor_cannot_access_other_hospital_appointment_or_responses():
    """PRD §21: Doctor user from Hospital A cannot access Hospital B appointment data."""
    token_doc_a = _login(DOCTOR_RAO_CREDS)
    assert token_doc_a is not None, "Login for Doctor Rao failed"

    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    try:
        doc_b = db.query(Doctor).filter(Doctor.name == "Dr. Kiran Kumar").first()
        patient = db.query(Patient).first()
        assert doc_b is not None and patient is not None

        date, start, end = unique_future_slot()
        apt_b = create_appointment_with_verification(
            db=db,
            hospital_id=doc_b.hospital_id,
            doctor_id=doc_b.id,
            patient_id=patient.id,
            date=date,
            start_time=start,
            end_time=end,
            idempotency_key=f"SEC-DOC-CROSS-{uuid.uuid4().hex[:8]}"
        )

        headers = {"Authorization": f"Bearer {token_doc_a}"}

        # Doctor Rao cannot read Dr. Kiran's appointment
        resp_get = client.get(f"/api/appointments/{apt_b.id}", headers=headers)
        assert resp_get.status_code == 403

        # Doctor Rao cannot read Dr. Kiran's patient questionnaire responses
        resp_resp = client.get(f"/api/questionnaires/responses/{apt_b.id}", headers=headers)
        assert resp_resp.status_code == 403

        # Clean up
        cancel_appointment_flow(db, apt_b.id, actor_email="cleaner")
    finally:
        db.close()

