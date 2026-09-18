import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.database import Base

class DoctorStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    BOOKED = "BOOKED"

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    specialty_id = Column(Integer, ForeignKey("specialties.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    photo = Column(String(500), nullable=True)
    qualifications = Column(String(255), nullable=False, default="MBBS, MD")
    experience = Column(Integer, default=5) # years
    languages = Column(String(255), default="English, Telugu, Hindi")
    consultation_types = Column(String(255), default="IN_PERSON,VIDEO")
    appointment_duration = Column(Integer, default=30) # minutes
    external_provider_id = Column(String(100), nullable=True, index=True)
    status = Column(Enum(DoctorStatus), default=DoctorStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    hospital = relationship("Hospital", back_populates="doctors")
    user = relationship("User", back_populates="doctor_profile")
    department = relationship("Department", back_populates="doctors")
    specialty = relationship("Specialty", back_populates="doctors")
    calendars = relationship("Calendar", back_populates="doctor", cascade="all, delete-orphan")
    availabilities = relationship("Availability", back_populates="doctor", cascade="all, delete-orphan")
    blocked_slots = relationship("BlockedSlot", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor")

class Calendar(Base):
    __tablename__ = "calendars"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), default="Primary Schedule")
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor", back_populates="calendars")
    availabilities = relationship("Availability", back_populates="calendar", cascade="all, delete-orphan")

class Availability(Base):
    __tablename__ = "availabilities"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    calendar_id = Column(Integer, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(20), nullable=False, index=True) # YYYY-MM-DD
    start_time = Column(String(10), nullable=False)       # HH:MM
    end_time = Column(String(10), nullable=False)         # HH:MM
    status = Column(Enum(AvailabilityStatus), default=AvailabilityStatus.AVAILABLE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor", back_populates="availabilities")
    calendar = relationship("Calendar", back_populates="availabilities")

class BlockedSlot(Base):
    __tablename__ = "blocked_slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(20), nullable=False, index=True) # YYYY-MM-DD
    start_time = Column(String(10), nullable=False)       # HH:MM
    end_time = Column(String(10), nullable=False)         # HH:MM
    reason = Column(String(255), default="Doctor on leave / Meeting")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor", back_populates="blocked_slots")
