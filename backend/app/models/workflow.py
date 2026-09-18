from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    trigger_event = Column(String(100), nullable=False) # APPOINTMENT_CONFIRMED, QUESTIONNAIRE_COMPLETED
    steps_definition = Column(JSON, nullable=False) # list of steps: [{"step": 1, "action": "ASSIGN_QUESTIONNAIRE", "delay_sec": 0}, {"step": 2, "action": "SEND_REMINDER", "delay_sec": 5}]
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="RUNNING", nullable=False) # RUNNING, COMPLETED, FAILED, RETRYING
    current_step = Column(Integer, default=1, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    execution_log = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    idempotency_key = Column(String(100), nullable=True, index=True)

    workflow = relationship("Workflow", back_populates="executions")
    appointment = relationship("Appointment", back_populates="workflow_executions")
