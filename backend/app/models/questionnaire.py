import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class QuestionType(str, enum.Enum):
    YES_NO = "YES_NO"
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    NUMERIC = "NUMERIC"
    DATE = "DATE"
    SHORT_TEXT = "SHORT_TEXT"
    LONG_TEXT = "LONG_TEXT"

class QuestionnaireStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    ARCHIVED = "ARCHIVED"

class ResponseStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"

class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True)
    specialty_id = Column(Integer, ForeignKey("specialties.id", ondelete="SET NULL"), nullable=True)
    appointment_type = Column(String(50), nullable=True)
    name = Column(String(255), nullable=False)
    status = Column(Enum(QuestionnaireStatus), default=QuestionnaireStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    questions = relationship("QuestionnaireQuestion", back_populates="questionnaire", cascade="all, delete-orphan")
    responses = relationship("QuestionnaireResponse", back_populates="questionnaire")

class QuestionnaireQuestion(Base):
    __tablename__ = "questionnaire_questions"

    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(String(500), nullable=False)
    type = Column(Enum(QuestionType), nullable=False)
    options = Column(Text, nullable=True) # JSON list or comma-delimited strings
    required = Column(Boolean, default=True, nullable=False)
    order = Column(Integer, default=1, nullable=False)

    questionnaire = relationship("Questionnaire", back_populates="questions")

class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    responses = Column(JSON, nullable=False) # Dict of {question_id: answer}
    status = Column(Enum(ResponseStatus), default=ResponseStatus.SUBMITTED, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    questionnaire = relationship("Questionnaire", back_populates="responses")
    appointment = relationship("Appointment", back_populates="questionnaire_responses")
    patient = relationship("Patient", back_populates="questionnaire_responses")
