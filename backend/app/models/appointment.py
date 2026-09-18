import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class AppointmentStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    FAILED = "FAILED"
    SYNCHRONIZATION_PENDING = "SYNCHRONIZATION_PENDING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_type = Column(String(50), default="IN_PERSON", nullable=False) # IN_PERSON, VIDEO, FOLLOW_UP
    date = Column(String(20), nullable=False, index=True) # YYYY-MM-DD
    start_time = Column(String(10), nullable=False)       # HH:MM
    end_time = Column(String(10), nullable=False)         # HH:MM
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False, index=True)
    external_appointment_id = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=False, unique=True, index=True)
    reason = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital = relationship("Hospital", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    questionnaire_responses = relationship("QuestionnaireResponse", back_populates="appointment")
    workflow_executions = relationship("WorkflowExecution", back_populates="appointment")
    notifications = relationship("Notification", back_populates="appointment")
    state_history = relationship("AppointmentStateHistory", back_populates="appointment", cascade="all, delete-orphan", order_by="AppointmentStateHistory.id.asc()")

class AppointmentStateHistory(Base):
    __tablename__ = "appointment_state_history"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    reason = Column(String(255), nullable=True)
    actor = Column(String(255), nullable=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="state_history")

VALID_STATE_TRANSITIONS = {
    AppointmentStatus.REQUESTED: [AppointmentStatus.PENDING, AppointmentStatus.FAILED, AppointmentStatus.CANCELLED],
    AppointmentStatus.PENDING: [AppointmentStatus.CONFIRMED, AppointmentStatus.SYNCHRONIZATION_PENDING, AppointmentStatus.FAILED, AppointmentStatus.CANCELLED, AppointmentStatus.RECONCILIATION_REQUIRED],
    AppointmentStatus.SYNCHRONIZATION_PENDING: [AppointmentStatus.CONFIRMED, AppointmentStatus.FAILED, AppointmentStatus.RECONCILIATION_REQUIRED],
    AppointmentStatus.CONFIRMED: [AppointmentStatus.RESCHEDULED, AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW],
    AppointmentStatus.RESCHEDULED: [AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULED, AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW],
    AppointmentStatus.RECONCILIATION_REQUIRED: [AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED, AppointmentStatus.FAILED],
    AppointmentStatus.CANCELLED: [], # Terminal state
    AppointmentStatus.COMPLETED: [], # Terminal state
    AppointmentStatus.NO_SHOW: [],   # Terminal state
    AppointmentStatus.FAILED: [AppointmentStatus.PENDING, AppointmentStatus.CANCELLED]
}

def can_transition_appointment(from_status: AppointmentStatus, to_status: AppointmentStatus) -> bool:
    if from_status == to_status:
        return True
    allowed = VALID_STATE_TRANSITIONS.get(from_status, [])
    return to_status in allowed


class ExternalMapping(Base):
    __tablename__ = "external_mappings"
    __table_args__ = (
        UniqueConstraint("entity_type", "internal_id", "system_name", name="uq_entity_internal_system"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False) # PATIENT, DOCTOR, FACILITY, APPOINTMENT
    internal_id = Column(Integer, nullable=False, index=True)
    external_id = Column(String(100), nullable=False, index=True)
    system_name = Column(String(50), default="MOCK_EHR", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
