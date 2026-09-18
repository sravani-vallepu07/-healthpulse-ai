from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from app.database import Base

class IntegrationOperation(Base):
    __tablename__ = "integration_operations"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    operation_type = Column(String(100), nullable=False) # CREATE_APPOINTMENT, VERIFY, CANCEL, UPDATE
    external_system = Column(String(50), default="MOCK_EHR", nullable=False)
    status = Column(String(50), nullable=False) # PENDING, SUCCESS, FAILED, UNKNOWN
    request_id = Column(String(100), nullable=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    error = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class IntegrationVerification(Base):
    __tablename__ = "integration_verifications"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id = Column(String(100), nullable=True)
    verification_status = Column(String(50), nullable=False) # VERIFIED, MISMATCH, NOT_FOUND, ERROR
    verification_result = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    failure_type = Column(String(100), nullable=False) # TIMEOUT, NETWORK_ERROR, SLOT_CONFLICT, UNKNOWN_OUTCOME
    external_state = Column(String(100), nullable=False)
    internal_state = Column(String(100), nullable=False)
    resolution = Column(Text, nullable=True)
    status = Column(String(50), default="RECONCILIATION_REQUIRED", nullable=False) # RECONCILIATION_REQUIRED, RESOLVED, ESCALATED_TO_HUMAN
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
