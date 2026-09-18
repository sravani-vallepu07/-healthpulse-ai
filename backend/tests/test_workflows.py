"""
Workflow Service Tests - idempotency, conditional branching, retries, execution log.
"""
import uuid
import pytest
from app.database import SessionLocal
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import AppointmentStatus
from app.models.workflow import WorkflowExecution
from app.models.questionnaire import Questionnaire, QuestionnaireStatus
from app.services.appointment_service import create_appointment_with_verification, cancel_appointment_flow
from app.services.workflow_service import trigger_appointment_workflow
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode
from tests.conftest import unique_future_slot


def _book_appointment(db):
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    doctor = db.query(Doctor).filter(Doctor.status == "ACTIVE").first()
    patient = db.query(Patient).first()
    assert doctor and patient
    date, start, end = unique_future_slot()
    apt = create_appointment_with_verification(
        db=db, hospital_id=doctor.hospital_id, doctor_id=doctor.id,
        patient_id=patient.id, date=date, start_time=start, end_time=end,
        idempotency_key=f"WF-TEST-{uuid.uuid4().hex[:8]}"
    )
    assert apt.status == AppointmentStatus.CONFIRMED
    return apt


def test_workflow_execution_is_created():
    """Workflow-1: Triggering workflow creates a WorkflowExecution record."""
    db = SessionLocal()
    try:
        apt = _book_appointment(db)
        execution = trigger_appointment_workflow(db, apt, idempotency_key=f"WF-EX-{uuid.uuid4().hex[:8]}")
        assert execution is not None
        assert execution.id is not None
        assert execution.appointment_id == apt.id
        assert execution.status in ("COMPLETED", "COMPLETED_WITH_ERRORS")
        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        db.close()


def test_workflow_idempotency():
    """Workflow-2: Same idempotency key returns same execution — no duplicate."""
    db = SessionLocal()
    try:
        apt = _book_appointment(db)
        idem_key = f"WF-IDEM-{uuid.uuid4().hex[:8]}"
        exec1 = trigger_appointment_workflow(db, apt, idempotency_key=idem_key)
        exec2 = trigger_appointment_workflow(db, apt, idempotency_key=idem_key)
        assert exec1 is not None and exec2 is not None
        assert exec1.id == exec2.id, "Idempotency violated: duplicate workflow execution created"
        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        db.close()


def test_workflow_execution_log_has_required_steps():
    """Workflow-3: Execution log records CHECK_QUESTIONNAIRE, NOTIFY_PATIENT, NOTIFY_DOCTOR."""
    db = SessionLocal()
    try:
        apt = _book_appointment(db)
        idem_key = f"WF-LOG-{uuid.uuid4().hex[:8]}"
        execution = trigger_appointment_workflow(db, apt, idempotency_key=idem_key)
        assert isinstance(execution.execution_log, list)
        assert len(execution.execution_log) >= 3
        actions = [step["action"] for step in execution.execution_log]
        assert "CHECK_QUESTIONNAIRE" in actions
        assert "NOTIFY_PATIENT" in actions
        assert "NOTIFY_DOCTOR" in actions
        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        db.close()


def test_workflow_conditional_branch_questionnaire():
    """Workflow-4: Conditional branch records correct status based on questionnaire availability."""
    db = SessionLocal()
    try:
        apt = _book_appointment(db)
        idem_key = f"WF-BRANCH-{uuid.uuid4().hex[:8]}"
        execution = trigger_appointment_workflow(db, apt, idempotency_key=idem_key)

        log = execution.execution_log
        check_step = next((s for s in log if s["action"] == "CHECK_QUESTIONNAIRE"), None)
        assign_step = next((s for s in log if s["action"] == "ASSIGN_QUESTIONNAIRE"), None)
        assert check_step is not None

        questionnaire = db.query(Questionnaire).filter(
            Questionnaire.hospital_id == apt.hospital_id,
            Questionnaire.status == QuestionnaireStatus.ACTIVE
        ).first()

        if questionnaire:
            assert check_step["branch"] == "QUESTIONNAIRE_AVAILABLE"
            assert assign_step is not None and assign_step["status"] == "SUCCESS"
        else:
            assert check_step["branch"] == "NO_QUESTIONNAIRE"
            assert assign_step is not None and assign_step["status"] == "SKIPPED"

        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        db.close()


def test_workflow_stores_idempotency_and_correlation_keys():
    """Workflow-5: WorkflowExecution stores both idempotency_key and correlation_id."""
    db = SessionLocal()
    try:
        apt = _book_appointment(db)
        idem_key = f"WF-KEYS-{uuid.uuid4().hex[:8]}"
        corr_id = f"WF-CORR-{uuid.uuid4().hex[:6].upper()}"
        execution = trigger_appointment_workflow(db, apt, idempotency_key=idem_key, correlation_id=corr_id)
        assert execution.idempotency_key == idem_key
        assert execution.correlation_id == corr_id
        cancel_appointment_flow(db, apt.id, actor_email="test_cleaner")
    finally:
        db.close()
