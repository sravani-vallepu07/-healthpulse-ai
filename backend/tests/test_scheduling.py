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


def test_concurrent_booking_double_booking_prevention():
    """
    PRD §7 / §25 Concurrency Test:
    Simultaneously fires two booking requests for the exact same slot.
    Asserts that DB-level transactional constraints ensure exactly ONE succeeds
    and the other fails with HTTP 409 SLOT_CONFLICT.
    """
    import uuid
    import concurrent.futures
    from fastapi import HTTPException
    from app.models.patient import Patient
    from app.services.appointment_service import create_appointment_with_verification, cancel_appointment_flow
    from tests.conftest import unique_future_slot

    db_setup = SessionLocal()
    try:
        doctor = db_setup.query(Doctor).filter(Doctor.status == DoctorStatus.ACTIVE).first()
        patient1 = db_setup.query(Patient).first()
        patient2 = db_setup.query(Patient).offset(1).first() or patient1
        assert doctor is not None
        assert patient1 is not None

        test_date, test_start, test_end = unique_future_slot()
    finally:
        db_setup.close()

    def book_slot(pat_id: int, idem_suffix: str):
        thread_db = SessionLocal()
        try:
            apt = create_appointment_with_verification(
                db=thread_db,
                hospital_id=doctor.hospital_id,
                doctor_id=doctor.id,
                patient_id=pat_id,
                date=test_date,
                start_time=test_start,
                end_time=test_end,
                idempotency_key=f"CONCUR-{uuid.uuid4().hex[:6]}-{idem_suffix}"
            )
            return ("SUCCESS", apt.id)
        except HTTPException as he:
            return ("HTTP_ERROR", he.status_code, he.detail)
        except Exception as e:
            return ("EXCEPTION", str(e))
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(book_slot, patient1.id, "REQ1")
        f2 = executor.submit(book_slot, patient2.id, "REQ2")
        res1 = f1.result()
        res2 = f2.result()

    all_res = [res1, res2]
    successes = [r for r in all_res if r[0] == "SUCCESS"]
    conflicts = [r for r in all_res if r[0] == "HTTP_ERROR" and r[1] == 409]

    assert len(successes) == 1, f"Expected exactly 1 booking to succeed, got {len(successes)}: {all_res}"
    assert len(conflicts) == 1, f"Expected exactly 1 conflict (409), got {len(conflicts)}: {all_res}"
    assert "SLOT_CONFLICT" in str(conflicts[0][2]), f"Expected SLOT_CONFLICT error code: {conflicts}"

    # Clean up the successful booking
    cleanup_db = SessionLocal()
    try:
        succ_apt_id = successes[0][1]
        cancel_appointment_flow(cleanup_db, succ_apt_id, actor_email="cleanup")
    finally:
        cleanup_db.close()

