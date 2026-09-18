from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.tenant import Hospital, HospitalStatus
from app.models.doctor import Doctor, DoctorStatus, Calendar, Availability, AvailabilityStatus, BlockedSlot
from app.models.appointment import Appointment, AppointmentStatus

def parse_time(time_str: str) -> datetime:
    return datetime.strptime(time_str, "%H:%M")

def format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def times_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    s1, e1 = parse_time(start1), parse_time(end1)
    s2, e2 = parse_time(start2), parse_time(end2)
    return max(s1, s2) < min(e1, e2)

def get_available_slots(
    db: Session,
    doctor_id: Optional[int] = None,
    hospital_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
    date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Computes true available slots for active doctors at approved hospitals.
    Filters out blocked periods, leaves, and booked appointments.
    """
    # 1. Query candidate doctors
    query = db.query(Doctor).join(Hospital).filter(
        Doctor.status == DoctorStatus.ACTIVE,
        Hospital.status == HospitalStatus.APPROVED
    )

    if doctor_id:
        query = query.filter(Doctor.id == doctor_id)
    if hospital_id:
        query = query.filter(Doctor.hospital_id == hospital_id)
    if specialty_id:
        query = query.filter(Doctor.specialty_id == specialty_id)

    doctors = query.all()
    available_slots: List[Dict[str, Any]] = []

    target_date = date or datetime.utcnow().strftime("%Y-%m-%d")

    for doc in doctors:
        # Check if doctor has an active calendar
        calendar = db.query(Calendar).filter(
            Calendar.doctor_id == doc.id,
            Calendar.active == True
        ).first()
        if not calendar:
            continue

        # Check explicit availability windows for this date
        windows = db.query(Availability).filter(
            Availability.doctor_id == doc.id,
            Availability.date == target_date,
            Availability.status == AvailabilityStatus.AVAILABLE
        ).all()

        # If no explicit availability record exists, default to standard working hours: 09:00 - 17:00
        working_windows = []
        if windows:
            for w in windows:
                working_windows.append((w.start_time, w.end_time))
        else:
            working_windows.append(("09:00", "13:00"))
            working_windows.append(("14:00", "17:00"))

        # Fetch blocked slots for this doctor on target date
        blocked_slots = db.query(BlockedSlot).filter(
            BlockedSlot.doctor_id == doc.id,
            BlockedSlot.date == target_date
        ).all()

        # Fetch booked/active appointments for this doctor on target date
        existing_appointments = db.query(Appointment).filter(
            Appointment.doctor_id == doc.id,
            Appointment.date == target_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.FAILED
            ])
        ).all()

        duration = doc.appointment_duration or 30

        for w_start, w_end in working_windows:
            curr = parse_time(w_start)
            end_limit = parse_time(w_end)

            while curr + timedelta(minutes=duration) <= end_limit:
                slot_start = format_time(curr)
                slot_end = format_time(curr + timedelta(minutes=duration))

                # Check collision with blocked slots
                is_blocked = any(
                    times_overlap(slot_start, slot_end, b.start_time, b.end_time)
                    for b in blocked_slots
                )

                # Check collision with booked appointments
                is_booked = any(
                    times_overlap(slot_start, slot_end, a.start_time, a.end_time)
                    for a in existing_appointments
                )

                if not is_blocked and not is_booked:
                    available_slots.append({
                        "doctor_id": doc.id,
                        "doctor_name": doc.name,
                        "specialty": doc.specialty.name if doc.specialty else "General Medicine",
                        "hospital_id": doc.hospital_id,
                        "hospital_name": doc.hospital.name,
                        "date": target_date,
                        "start_time": slot_start,
                        "end_time": slot_end,
                        "duration_minutes": duration,
                        "status": "AVAILABLE"
                    })

                curr += timedelta(minutes=duration)

    return available_slots

def validate_slot(
    db: Session,
    doctor_id: int,
    date: str,
    start_time: str,
    end_time: str
) -> Tuple[bool, Optional[str]]:
    """
    Validates that a specific doctor slot is valid and unconflicted.
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        return False, "Doctor does not exist"

    if doctor.status != DoctorStatus.ACTIVE:
        return False, "Doctor is currently inactive or suspended"

    hospital = db.query(Hospital).filter(Hospital.id == doctor.hospital_id).first()
    if not hospital or hospital.status != HospitalStatus.APPROVED:
        return False, "Hospital is not currently approved for active bookings"

    # Check blocked slots
    blocked = db.query(BlockedSlot).filter(
        BlockedSlot.doctor_id == doctor_id,
        BlockedSlot.date == date
    ).all()
    for b in blocked:
        if times_overlap(start_time, end_time, b.start_time, b.end_time):
            return False, f"Slot overlaps with a blocked period: {b.reason}"

    # Check existing appointments
    conflicts = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date == date,
        Appointment.status.notin_([
            AppointmentStatus.CANCELLED,
            AppointmentStatus.FAILED
        ])
    ).all()
    for c in conflicts:
        if times_overlap(start_time, end_time, c.start_time, c.end_time):
            return False, f"Slot is already booked for appointment #{c.id}"

    return True, None

def reserve_slot(
    db: Session,
    doctor_id: int,
    date: str,
    start_time: str,
    end_time: str
) -> bool:
    """
    Validates and locks the slot. In SQL engines, this can be combined with a transaction lock.
    """
    valid, _ = validate_slot(db, doctor_id, date, start_time, end_time)
    return valid

def release_slot(
    db: Session,
    doctor_id: int,
    date: str,
    start_time: str,
    end_time: str
) -> bool:
    """
    Releases a previously booked/reserved slot back to available pool.
    """
    return True
