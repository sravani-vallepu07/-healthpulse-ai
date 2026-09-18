from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit import Notification

def create_notification(
    db: Session,
    recipient_id: int,
    role: str,
    notif_type: str,
    title: str,
    message: str,
    appointment_id: Optional[int] = None
) -> Notification:
    """
    Creates an in-app notification for a user (patient, doctor, or hospital admin).
    """
    notification = Notification(
        recipient_id=recipient_id,
        role=role,
        type=notif_type,
        title=title,
        message=message,
        status="UNREAD",
        appointment_id=appointment_id
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification
