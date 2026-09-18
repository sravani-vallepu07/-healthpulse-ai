"""
EHR Recovery Tests - timeout/unknown outcome recovery flow.
"""
import uuid
import pytest
from app.database import SessionLocal
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import AppointmentStatus
from app.models.integration import IntegrationOperation, IntegrationVerification
from app.services.appointment_service import create_appointment_with_verification, cancel_appointment_flow
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode
from tests.conftest import unique_future_slot


def test_unknown_outcome_and_timeout_recovery():
    """
    EHR timeout scenario:
    1. TIMEOUT failure mode — EHR creates record but raises TimeoutError
    2. Backend marks operation UNKNOWN
    3. Verification phase finds the record in EHR
    4. Appointment confirmed without duplicate creation
    """
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.TIMEOUT)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        assert doctor and patient

        date, start, end = unique_future_slot()
        corr_id = f"TEST-TIMEOUT-{uuid.uuid4().hex[:6].upper()}"
        idem_key = f"IDEM-TIMEOUT-{uuid.uuid4().hex[:8]}"

        apt = create_appointment_with_verification(
            db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
            patient_id=patient.id, date=date, start_time=start, end_time=end,
            correlation_id=corr_id, idempotency_key=idem_key
        )

        assert apt is not None
        assert apt.status == AppointmentStatus.CONFIRMED
        assert apt.external_appointment_id is not None
        assert apt.external_appointment_id.startswith("EXT-APT-")

        op = db.query(IntegrationOperation).filter(
            IntegrationOperation.correlation_id == corr_id,
            IntegrationOperation.status == "UNKNOWN"
        ).first()
        assert op is not None

        verif = db.query(IntegrationVerification).filter(
            IntegrationVerification.appointment_id == apt.id
        ).first()
        assert verif is not None
        assert verif.verification_status == "VERIFIED"
        assert verif.verification_result.get("verified_from_unknown_outcome") is True

        mock_ehr_connector.set_failure_mode(FailureMode.NONE)
        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        mock_ehr_connector.set_failure_mode(FailureMode.NONE)
        db.close()


def test_not_found_after_non_timeout_goes_to_reconciliation():
    """
    When EHR immediately fails (non-timeout) and record not found,
    the appointment goes to FAILED state (not RECONCILIATION_REQUIRED since no unknown_outcome).
    """
    from fastapi import HTTPException
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.FAIL)
    try:
        doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
        patient = db.query(Patient).first()
        if not doctor or not patient:
            pytest.skip("Need doctor and patient in DB")

        date, start, end = unique_future_slot()

        with pytest.raises(HTTPException) as exc_info:
            create_appointment_with_verification(
                db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
                patient_id=patient.id, date=date, start_time=start, end_time=end,
                idempotency_key=f"IDEM-FAIL-{uuid.uuid4().hex[:8]}"
            )
        # Should be a 502 EHR_INTEGRATION_FAILED or 500 RECONCILIATION_REQUIRED
        assert exc_info.value.status_code in (500, 502)
    finally:
        mock_ehr_connector.set_failure_mode(FailureMode.NONE)
        db.close()
