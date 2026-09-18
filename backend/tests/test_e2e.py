import uuid
import pytest
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.patient import Patient, User, Role
from app.models.doctor import Doctor
from app.models.appointment import Appointment, AppointmentStatus
from app.models.questionnaire import Questionnaire, QuestionnaireResponse
from app.models.audit import AuditEvent, Notification
from app.models.workflow import WorkflowExecution
from app.services.appointment_service import create_appointment_with_verification, cancel_appointment_flow
from app.services.workflow_service import trigger_questionnaire_completed_workflow
from app.ai.capabilities import AICapabilities
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode

def test_complete_end_to_end_chain():
    """
    Validates complete chain:
    Patient Request
    -> AI Understanding + Context
    -> Hospital / Doctor Discovery
    -> Real Availability
    -> Authorized Action
    -> Healthcare-System Integration (Mock EHR)
    -> External Verification
    -> State Synchronization
    -> Questionnaire / Workflow / Notification
    -> Doctor Visibility
    -> Admin Visibility / Analytics / Audit
    """
    db = SessionLocal()
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)

    try:
        corr_id = f"E2E-{uuid.uuid4().hex[:8].upper()}"
        tools = AICapabilities(db, correlation_id=corr_id)

        # 1. Hospital & Doctor Discovery
        hospitals = tools.search_hospitals(city="Vijayawada")
        assert len(hospitals) >= 2

        doctors = tools.search_doctors(specialty="Orthopedics")
        assert len(doctors) >= 1
        ortho_doc = doctors[0]
        assert ortho_doc["name"] == "Dr. Anil Rao"

        # 2. Check Real Availability
        test_date = (datetime.utcnow() + timedelta(days=6)).strftime("%Y-%m-%d")
        slots = tools.check_availability(doctor_id=ortho_doc["id"], date=test_date)
        assert len(slots) > 0
        selected_slot = slots[0]

        # 3. Patient Info
        patient = db.query(Patient).first()
        assert patient is not None

        # 4. Authorized Booking & Verification Flow
        apt_result = tools.create_appointment(
            hospital_id=selected_slot["hospital_id"],
            doctor_id=selected_slot["doctor_id"],
            patient_id=patient.id,
            date=test_date,
            start_time=selected_slot["start_time"],
            end_time=selected_slot["end_time"],
            reason="Knee pain pre-visit intake"
        )
        assert apt_result["status"] == "CONFIRMED"
        assert apt_result["external_id"] is not None
        apt_id = apt_result["appointment_id"]

        # 5. External EHR verification check
        ehr_record = mock_ehr_connector.verify_appointment(external_id=apt_result["external_id"])
        assert ehr_record is not None
        assert ehr_record["status"] == "SCHEDULED"

        # 6. Workflow & Questionnaire Assignment Check
        wf_exec = db.query(WorkflowExecution).filter(WorkflowExecution.appointment_id == apt_id).first()
        assert wf_exec is not None
        assert wf_exec.status == "COMPLETED"

        # Check in-app notification to patient
        pat_notif = db.query(Notification).filter(
            Notification.recipient_id == patient.user_id,
            Notification.appointment_id == apt_id
        ).first()
        assert pat_notif is not None
        assert "confirmed" in pat_notif.message.lower()

        # 7. Patient Pre-Visit Questionnaire Submission
        q_data = tools.get_questionnaire(hospital_id=selected_slot["hospital_id"])
        assert q_data is not None
        q_id = q_data["questionnaire_id"]

        sample_answers = {
            "joint_area": "Right Knee",
            "duration": "1-4 weeks",
            "pain_scale": 6,
            "prior_surgery": False
        }
        submit_res = tools.submit_questionnaire(
            questionnaire_id=q_id,
            appointment_id=apt_id,
            patient_id=patient.id,
            responses=sample_answers
        )
        assert submit_res["status"] == "SUBMITTED"

        # 8. Doctor Visibility: Verify doctor can retrieve pre-visit questionnaire responses
        saved_resp = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.appointment_id == apt_id
        ).first()
        assert saved_resp is not None
        assert saved_resp.responses["joint_area"] == "Right Knee"

        # 9. Audit Trail Check
        audit_events = db.query(AuditEvent).filter(AuditEvent.correlation_id == corr_id).all()
        assert len(audit_events) > 0

        # Clean up
        cancel_appointment_flow(db, apt_id, actor_email="test_e2e_cleaner")
    finally:
        db.close()
