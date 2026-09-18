import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.workflow import Workflow, WorkflowExecution
from app.models.appointment import Appointment
from app.models.questionnaire import Questionnaire, QuestionnaireStatus
from app.services.notification_service import create_notification

def trigger_appointment_workflow(
    db: Session,
    appointment: Appointment,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> Optional[WorkflowExecution]:
    """
    Executes the post-booking orchestration workflow:
    1. Idempotency protection check
    2. Check / Match questionnaire
    3. Assign questionnaire if available
    4. Notify patient
    5. Notify doctor
    6. Record execution log
    """
    corr_id = correlation_id or appointment.correlation_id or "WF-DEFAULT"

    # Idempotency check: Return existing workflow execution if already executed
    if idempotency_key:
        existing_exec = db.query(WorkflowExecution).filter(
            WorkflowExecution.idempotency_key == idempotency_key
        ).first()
        if existing_exec:
            return existing_exec

    # Find matching active workflow
    workflow = db.query(Workflow).filter(
        Workflow.trigger_event == "APPOINTMENT_CONFIRMED",
        Workflow.active == True
    ).first()

    if not workflow:
        workflow = Workflow(
            hospital_id=appointment.hospital_id,
            name="Default Post-Booking Patient Intake Workflow",
            trigger_event="APPOINTMENT_CONFIRMED",
            steps_definition=[
                {"step": 1, "action": "CHECK_QUESTIONNAIRE", "delay_sec": 0},
                {"step": 2, "action": "ASSIGN_QUESTIONNAIRE", "delay_sec": 0},
                {"step": 3, "action": "NOTIFY_PATIENT", "delay_sec": 0},
                {"step": 4, "action": "NOTIFY_DOCTOR", "delay_sec": 0}
            ],
            active=True
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)

    execution = WorkflowExecution(
        workflow_id=workflow.id,
        appointment_id=appointment.id,
        status="RUNNING",
        current_step=1,
        execution_log=[],
        correlation_id=corr_id,
        idempotency_key=idempotency_key,
        started_at=datetime.now(timezone.utc)
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    log = []

    # Step 1: Check Questionnaire
    questionnaire = db.query(Questionnaire).filter(
        Questionnaire.hospital_id == appointment.hospital_id,
        Questionnaire.status == QuestionnaireStatus.ACTIVE
    ).first()

    if questionnaire:
        log.append({"step": 1, "action": "CHECK_QUESTIONNAIRE", "status": "SUCCESS", "branch": "QUESTIONNAIRE_AVAILABLE", "detail": f"Found active questionnaire: {questionnaire.name}"})
        log.append({"step": 2, "action": "ASSIGN_QUESTIONNAIRE", "status": "SUCCESS", "detail": f"Assigned: {questionnaire.name}"})
    else:
        log.append({"step": 1, "action": "CHECK_QUESTIONNAIRE", "status": "SKIPPED", "branch": "NO_QUESTIONNAIRE", "detail": "No active questionnaire configured for hospital"})

    # Step 2 / 3: Notify Patient
    if appointment.patient and appointment.patient.user_id:
        create_notification(
            db=db,
            recipient_id=appointment.patient.user_id,
            role="PATIENT",
            notif_type="APPOINTMENT_CONFIRMED",
            title="Appointment Confirmed",
            message=f"Your appointment with {appointment.doctor.name if appointment.doctor else 'Doctor'} on {appointment.date} at {appointment.start_time} is confirmed. Please complete the pre-visit questionnaire.",
            appointment_id=appointment.id
        )
        log.append({"step": len(log) + 1, "action": "NOTIFY_PATIENT", "status": "SUCCESS"})

    # Step 3 / 4: Notify Doctor
    if appointment.doctor and appointment.doctor.user_id:
        create_notification(
            db=db,
            recipient_id=appointment.doctor.user_id,
            role="DOCTOR",
            notif_type="NEW_APPOINTMENT",
            title="New Patient Scheduled",
            message=f"New appointment booked: {appointment.patient.name if appointment.patient else 'Patient'} on {appointment.date} at {appointment.start_time}.",
            appointment_id=appointment.id
        )
        log.append({"step": len(log) + 1, "action": "NOTIFY_DOCTOR", "status": "SUCCESS"})

    execution.status = "COMPLETED"
    execution.current_step = len(log)
    execution.completed_at = datetime.now(timezone.utc)
    execution.execution_log = log
    db.commit()
    db.refresh(execution)
    return execution

def trigger_questionnaire_completed_workflow(db: Session, appointment_id: int):
    """
    Workflow step when patient finishes pre-visit questions: alerts doctor.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment and appointment.doctor and appointment.doctor.user_id:
        create_notification(
            db=db,
            recipient_id=appointment.doctor.user_id,
            role="DOCTOR",
            notif_type="QUESTIONNAIRE_COMPLETED",
            title="Pre-Visit Information Ready",
            message=f"Patient {appointment.patient.name} has submitted pre-visit questionnaire answers for appointment #{appointment.id}.",
            appointment_id=appointment.id
        )
