from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.ai import AIConversation, AIContext

def get_or_create_conversation(db: Session, patient_id: int, hospital_id: Optional[int] = None) -> AIConversation:
    conv = db.query(AIConversation).filter(
        AIConversation.patient_id == patient_id,
        AIConversation.status == "ACTIVE"
    ).order_by(AIConversation.id.desc()).first()

    if not conv:
        conv = AIConversation(
            patient_id=patient_id,
            hospital_id=hospital_id,
            current_intent="GENERAL_ADMINISTRATIVE_QUERY",
            status="ACTIVE"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        ctx = AIContext(
            conversation_id=conv.id,
            context_data={
                "selected_hospital_id": hospital_id,
                "selected_doctor_id": None,
                "selected_specialty": None,
                "selected_date": None,
                "last_suggested_slots": [],
                "current_appointment_id": None
            }
        )
        db.add(ctx)
        db.commit()
        db.refresh(conv)

    return conv

def get_context_data(db: Session, conversation_id: int) -> Dict[str, Any]:
    ctx = db.query(AIContext).filter(AIContext.conversation_id == conversation_id).first()
    if not ctx or not ctx.context_data:
        return {}
    return dict(ctx.context_data)

def update_context_data(db: Session, conversation_id: int, updates: Dict[str, Any]):
    ctx = db.query(AIContext).filter(AIContext.conversation_id == conversation_id).first()
    if ctx:
        current = dict(ctx.context_data or {})
        current.update(updates)
        ctx.context_data = current
        db.commit()
