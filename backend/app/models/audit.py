from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    event_type = Column(String(100), nullable=False, index=True) # APPOINTMENT_BOOKED, SLOT_RESERVED, EHR_SYNC, etc.
    resource_type = Column(String(100), nullable=False)          # APPOINTMENT, DOCTOR, HOSPITAL, QUESTIONNAIRE
    resource_id = Column(String(100), nullable=True)
    hospital_id = Column(Integer, nullable=True, index=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    safe_metadata = Column(JSON, nullable=True) # NEVER store raw sensitive PHI here
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    type = Column(String(100), nullable=False) # APPOINTMENT_CONFIRMED, APPOINTMENT_REMINDER, etc.
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="UNREAD", nullable=False) # UNREAD, READ
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="notifications")
