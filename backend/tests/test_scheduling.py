import pytest
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.tenant import Hospital, HospitalStatus
from app.models.doctor import Doctor, DoctorStatus, BlockedSlot
from app.models.appointment import Appointment, AppointmentStatus
from app.services.scheduling_service import get_available_slots, validate_slot

def test_available_slots_calculation():
    db = SessionLocal()
    try:
        doctor = db.query(Doctor).filter(Doctor.status == DoctorStatus.ACTIVE).first()
        assert doctor is not None

        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        slots = get_available_slots(db, doctor_id=doctor.id, date=today_str)
        assert len(slots) > 0
        assert all(s["doctor_id"] == doctor.id for s in slots)
        assert all(s["status"] == "AVAILABLE" for s in slots)
    finally:
        db.close()

def test_blocked_slot_exclusion():
    db = SessionLocal()
    try:
        doctor = db.query(Doctor).filter(Doctor.status == DoctorStatus.ACTIVE).first()
        assert doctor is not None

        test_date = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        # Add blocked slot
        blocked = BlockedSlot(
            doctor_id=doctor.id,
            date=test_date,
            start_time="10:00",
            end_time="11:00",
            reason="Surgery Conference"
        )
        db.add(blocked)
        db.commit()

        # Check validation
        valid, msg = validate_slot(db, doctor.id, test_date, "10:00", "10:30")
        assert not valid
        assert "overlaps with a blocked period" in msg

        # Ensure available slots do NOT include 10:00 or 10:30
        slots = get_available_slots(db, doctor_id=doctor.id, date=test_date)
        slot_times = [s["start_time"] for s in slots]
        assert "10:00" not in slot_times
        assert "10:30" not in slot_times

        # Clean up
        db.delete(blocked)
        db.commit()
    finally:
        db.close()

def test_inactive_doctor_rejected():
    db = SessionLocal()
    try:
        doctor = db.query(Doctor).filter(Doctor.status == DoctorStatus.ACTIVE).first()
        assert doctor is not None

        # Temporarily make doctor inactive
        doctor.status = DoctorStatus.INACTIVE
        db.commit()

        valid, msg = validate_slot(db, doctor.id, "2026-10-10", "10:00", "10:30")
        assert not valid
        assert "inactive" in msg.lower()

        # Restore
        doctor.status = DoctorStatus.ACTIVE
        db.commit()
    finally:
        db.close()
