from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.questionnaire import (
    Questionnaire, QuestionnaireQuestion, QuestionnaireResponse, 
    QuestionnaireStatus, ResponseStatus
)
from app.models.appointment import Appointment
from app.models.patient import User, Role
from app.schemas.schemas import (
    QuestionnaireCreate, QuestionnaireResponseCreate, StandardResponse
)
from app.auth.security import require_current_user, require_roles, verify_tenant_access
from app.services.workflow_service import trigger_questionnaire_completed_workflow
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/questionnaires", tags=["Questionnaires"])

@router.post("")
def create_questionnaire(
    payload: QuestionnaireCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    verify_tenant_access(user, payload.hospital_id)

    q = Questionnaire(
        hospital_id=payload.hospital_id,
        doctor_id=payload.doctor_id,
        specialty_id=payload.specialty_id,
        appointment_type=payload.appointment_type,
        name=payload.name,
        status=QuestionnaireStatus.ACTIVE
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    for question_item in payload.questions:
        qu = QuestionnaireQuestion(
            questionnaire_id=q.id,
            question=question_item.question,
            type=question_item.type,
            options=question_item.options,
            required=question_item.required,
            order=question_item.order
        )
        db.add(qu)

    db.commit()
    return {"success": True, "questionnaire_id": q.id, "name": q.name}

@router.get("")
def list_questionnaires(
    hospital_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Questionnaire).filter(Questionnaire.status == QuestionnaireStatus.ACTIVE)
    if hospital_id:
        query = query.filter(Questionnaire.hospital_id == hospital_id)
    if specialty_id:
        query = query.filter(Questionnaire.specialty_id == specialty_id)

    results = []
    for q in query.all():
        results.append({
            "id": q.id,
            "hospital_id": q.hospital_id,
            "name": q.name,
            "questions_count": len(q.questions)
        })
    return results

@router.get("/{questionnaire_id}")
def get_questionnaire(questionnaire_id: int, db: Session = Depends(get_db)):
    q = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
    if not q:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Questionnaire not found"})

    return {
        "id": q.id,
        "hospital_id": q.hospital_id,
        "name": q.name,
        "questions": [{
            "id": qu.id,
            "question": qu.question,
            "type": qu.type.value,
            "options": qu.options.split(",") if qu.options else [],
            "required": qu.required,
            "order": qu.order
        } for qu in sorted(q.questions, key=lambda x: x.order)]
    }

@router.post("/{questionnaire_id}/responses")
def submit_questionnaire_response(
    questionnaire_id: int,
    payload: QuestionnaireResponseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    appointment = db.query(Appointment).filter(Appointment.id == payload.appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    patient_id = appointment.patient_id

    resp = QuestionnaireResponse(
        questionnaire_id=questionnaire_id,
        appointment_id=payload.appointment_id,
        patient_id=patient_id,
        responses=payload.responses,
        status=ResponseStatus.SUBMITTED
    )
    db.add(resp)
    db.commit()
    db.refresh(resp)

    # Workflow notification to doctor
    trigger_questionnaire_completed_workflow(db, payload.appointment_id)

    log_audit_event(
        db=db,
        actor=user.email,
        role=user.role.value,
        event_type="QUESTIONNAIRE_SUBMITTED",
        resource_type="QUESTIONNAIRE_RESPONSE",
        resource_id=str(resp.id),
        hospital_id=appointment.hospital_id,
        correlation_id=appointment.correlation_id
    )

    return {"success": True, "response_id": resp.id, "status": "SUBMITTED"}

@router.get("/responses/{appointment_id}")
def get_appointment_responses(
    appointment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Appointment not found"})

    # Doctor or Patient or Admin can view
    if user.role == Role.DOCTOR and (not user.doctor_profile or user.doctor_profile.id != appointment.doctor_id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})
    elif user.role == Role.PATIENT and (not user.patient_profile or user.patient_profile.id != appointment.patient_id):
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied"})

    responses = db.query(QuestionnaireResponse).filter(
        QuestionnaireResponse.appointment_id == appointment_id
    ).all()

    output = []
    for r in responses:
        output.append({
            "response_id": r.id,
            "questionnaire_name": r.questionnaire.name if r.questionnaire else "Assessment",
            "responses": r.responses,
            "status": r.status.value,
            "created_at": r.created_at
        })
    return output
