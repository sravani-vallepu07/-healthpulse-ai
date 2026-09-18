from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    current_intent = Column(String(100), default="GENERAL_ADMINISTRATIVE_QUERY")
    status = Column(String(50), default="ACTIVE") # ACTIVE, COMPLETED, ESCALATED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="conversations")
    ai_context = relationship("AIContext", back_populates="conversation", uselist=False, cascade="all, delete-orphan")

class AIContext(Base):
    __tablename__ = "ai_contexts"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), unique=True, nullable=False)
    context_data = Column(JSON, nullable=False, default=dict) # selected_hospital, selected_doctor, selected_slot, current_appointment, preferences
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversation = relationship("AIConversation", back_populates="ai_context")

class CapabilityExecution(Base):
    __tablename__ = "capability_executions"

    id = Column(Integer, primary_key=True, index=True)
    capability_name = Column(String(100), nullable=False, index=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False) # SUCCESS, FAILED
    error = Column(Text, nullable=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
