from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditEvent, Notification
from app.models.patient import User, Role
from app.schemas.schemas import AuditEventOut, NotificationOut
from app.auth.security import require_current_user, require_roles

router = APIRouter(prefix="/audit", tags=["Audit & Observability"])

@router.get("/events", response_model=List[AuditEventOut])
def list_audit_events(
    correlation_id: Optional[str] = None,
    event_type: Optional[str] = None,
    hospital_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    q = db.query(AuditEvent)
    if user.role == Role.HOSPITAL_ADMIN:
        q = q.filter(AuditEvent.hospital_id == user.hospital_id)
    elif hospital_id:
        q = q.filter(AuditEvent.hospital_id == hospital_id)

    if correlation_id:
        q = q.filter(AuditEvent.correlation_id == correlation_id)
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)

    return q.order_by(AuditEvent.id.desc()).limit(100).all()

@router.get("/notifications", response_model=List[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    notifs = db.query(Notification).filter(
        Notification.recipient_id == user.id
    ).order_by(Notification.id.desc()).limit(50).all()
    return notifs

@router.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.status = "READ"
    db.commit()
    return {"success": True}
