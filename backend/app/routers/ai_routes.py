from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import User, Patient, Role
from app.models.ai import AIConversation, AIContext
from app.schemas.schemas import AIChatRequest, AIChatResponse, AIVoiceRequest
from app.auth.security import require_current_user
from app.ai.context import get_or_create_conversation, get_context_data
from app.ai.agent import run_ai_agent
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/ai", tags=["AI Patient Access Agent"])

@router.post("/chat", response_model=AIChatResponse)
def ai_chat_turn(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    patient_id = payload.patient_id
    if user.role == Role.PATIENT:
        if not user.patient_profile:
            # Auto-create profile if missing
            p = Patient(
                user_id=user.id,
                name=user.email.split("@")[0].capitalize(),
                email=user.email,
                phone="9848011223"
            )
            db.add(p)
            db.commit()
            db.refresh(p)
            patient_id = p.id
        else:
            patient_id = user.patient_profile.id
    elif not patient_id:
        # For testing / non-patient preview
        p = db.query(Patient).first()
        patient_id = p.id if p else 1

    # Load or initialize conversation
    if payload.conversation_id:
        conv = db.query(AIConversation).filter(AIConversation.id == payload.conversation_id).first()
        if not conv:
            conv = get_or_create_conversation(db, patient_id=patient_id, hospital_id=payload.hospital_id)
    else:
        conv = get_or_create_conversation(db, patient_id=patient_id, hospital_id=payload.hospital_id)

    # Run LangGraph stateful agent
    result = run_ai_agent(
        db=db,
        patient_id=patient_id,
        conversation_id=conv.id,
        message=payload.message,
        hospital_id=payload.hospital_id or conv.hospital_id,
        correlation_id=payload.correlation_id
    )

    conv.current_intent = result["intent"]
    if result["is_escalated"]:
        conv.status = "ESCALATED"
    db.commit()

    log_audit_event(
        db=db,
        actor=user.email,
        role="PATIENT",
        event_type="AI_CONVERSATION_TURN",
        resource_type="AI_CONVERSATION",
        resource_id=str(conv.id),
        hospital_id=conv.hospital_id,
        correlation_id=result["correlation_id"],
        safe_metadata={"intent": result["intent"], "capabilities": result["capabilities_called"]}
    )

    return AIChatResponse(
        conversation_id=conv.id,
        reply=result["reply"],
        intent=result["intent"],
        capabilities_called=result["capabilities_called"],
        slots_suggested=result["slots_suggested"],
        appointment_data=result["appointment_data"],
        correlation_id=result["correlation_id"],
        is_escalated=result["is_escalated"]
    )

@router.post("/voice", response_model=AIChatResponse)
def ai_voice_turn(
    payload: AIVoiceRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """
    Voice endpoint: receives speech transcription, invokes LangGraph agent,
    and returns textual response ready for browser Text-to-Speech (TTS).
    """
    chat_req = AIChatRequest(
        conversation_id=payload.conversation_id,
        message=payload.transcript,
        patient_id=payload.patient_id,
        correlation_id=payload.correlation_id
    )
    return ai_chat_turn(chat_req, db, user)

@router.get("/conversations/{conversation_id}")
def get_conversation_details(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    conv = db.query(AIConversation).filter(AIConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Conversation not found"})

    if user.role == Role.PATIENT and user.patient_profile and conv.patient_id != user.patient_profile.id:
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "Access denied to this conversation"})

    context = get_context_data(db, conversation_id)
    return {
        "conversation_id": conv.id,
        "patient_id": conv.patient_id,
        "hospital_id": conv.hospital_id,
        "current_intent": conv.current_intent,
        "status": conv.status,
        "structured_context": context,
        "created_at": conv.created_at
    }
