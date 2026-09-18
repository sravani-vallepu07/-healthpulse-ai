from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent

def log_audit_event(
    db: Session,
    actor: str,
    role: str,
    event_type: str,
    resource_type: str,
    resource_id: Optional[str],
    correlation_id: str,
    hospital_id: Optional[int] = None,
    safe_metadata: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """
    Logs an auditable event with correlation ID.
    Guarantees that sensitive medical details/PHI are not stored in audit logs.
    """
    event = AuditEvent(
        actor=actor,
        role=role,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        hospital_id=hospital_id,
        correlation_id=correlation_id,
        safe_metadata=safe_metadata or {}
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
