from datetime import datetime, timedelta
from app.database import SessionLocal, Base, engine
from app.models.tenant import Hospital, HospitalStatus, Department, Specialty
from app.models.doctor import Doctor, DoctorStatus, Calendar, Availability, AvailabilityStatus, BlockedSlot
from app.models.patient import User, Patient, Role
from app.models.questionnaire import (
    Questionnaire, QuestionnaireQuestion, QuestionType, QuestionnaireStatus
)
from app.models.workflow import Workflow
from app.auth.security import hash_password

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if already seeded
    if db.query(User).filter(User.email == "platform.admin@healthcare.org").first():
        print("Database already seeded.")
        db.close()
        return

    print("Seeding database...")

    # 1. Platform Admin
    platform_admin = User(
        email="platform.admin@healthcare.org",
        hashed_password=hash_password("Admin@123"),
        role=Role.PLATFORM_ADMIN,
        is_active=True
    )
    db.add(platform_admin)
    db.commit()

    # 2. Hospitals
    hosp_abc = Hospital(
        name="ABC Multi-Speciality Hospital",
        address="MG Road, Governorpet",
        city="Vijayawada",
        contact_phone="+91 866 247 1111",
        contact_email="contact@abchospital.org",
        status=HospitalStatus.APPROVED
    )
    hosp_xyz = Hospital(
        name="XYZ Healthcare Center",
        address="Ring Road, Benz Circle",
        city="Vijayawada",
        contact_phone="+91 866 248 2222",
        contact_email="info@xyzhealth.org",
        status=HospitalStatus.APPROVED
    )
    hosp_sunrise = Hospital(
        name="Sunrise Health Institute",
        address="Bunder Road, Labbipet",
        city="Vijayawada",
        contact_phone="+91 866 249 3333",
        contact_email="care@sunrisehealth.org",
        status=HospitalStatus.UNDER_REVIEW
    )
    db.add_all([hosp_abc, hosp_xyz, hosp_sunrise])
    db.commit()

    # 3. Hospital Admins
    admin_abc = User(
        email="admin.abc@hospital.org",
        hashed_password=hash_password("Admin@123"),
        role=Role.HOSPITAL_ADMIN,
        hospital_id=hosp_abc.id,
        is_active=True
    )
    admin_xyz = User(
        email="admin.xyz@hospital.org",
        hashed_password=hash_password("Admin@123"),
        role=Role.HOSPITAL_ADMIN,
        hospital_id=hosp_xyz.id,
        is_active=True
    )
    db.add_all([admin_abc, admin_xyz])
    db.commit()

    # 4. Departments & Specialties
    dept_ortho = Department(hospital_id=hosp_abc.id, name="Orthopedic Surgery", description="Bones, joints, and spine")
    dept_gen = Department(hospital_id=hosp_abc.id, name="Internal Medicine", description="Adult primary healthcare")
    dept_derma = Department(hospital_id=hosp_xyz.id, name="Dermatology", description="Skin, hair, and nails")
    dept_ped = Department(hospital_id=hosp_xyz.id, name="Pediatrics", description="Child healthcare")
    db.add_all([dept_ortho, dept_gen, dept_derma, dept_ped])
    db.commit()

    spec_ortho = Specialty(hospital_id=hosp_abc.id, name="Orthopedics", description="Musculoskeletal system")
    spec_gen = Specialty(hospital_id=hosp_abc.id, name="General Medicine", description="Primary adult care")
    spec_derma = Specialty(hospital_id=hosp_xyz.id, name="Dermatology", description="Dermatologic care")
    spec_ped = Specialty(hospital_id=hosp_xyz.id, name="Pediatrics", description="Pediatric care")
    db.add_all([spec_ortho, spec_gen, spec_derma, spec_ped])
    db.commit()

    # 5. Doctors & User Accounts
    u_rao = User(email="dr.anil.rao@hospital.org", hashed_password=hash_password("Doctor@123"), role=Role.DOCTOR, hospital_id=hosp_abc.id)
    u_sharma = User(email="dr.priya.sharma@hospital.org", hashed_password=hash_password("Doctor@123"), role=Role.DOCTOR, hospital_id=hosp_abc.id)
    u_kiran = User(email="dr.kiran.kumar@hospital.org", hashed_password=hash_password("Doctor@123"), role=Role.DOCTOR, hospital_id=hosp_xyz.id)
    u_sunita = User(email="dr.sunita.reddy@hospital.org", hashed_password=hash_password("Doctor@123"), role=Role.DOCTOR, hospital_id=hosp_xyz.id)
    db.add_all([u_rao, u_sharma, u_kiran, u_sunita])
    db.commit()

    doc_rao = Doctor(
        hospital_id=hosp_abc.id,
        user_id=u_rao.id,
        department_id=dept_ortho.id,
        specialty_id=spec_ortho.id,
        name="Dr. Anil Rao",
        qualifications="MBBS, MS (Orthopedics), MCh",
        experience=14,
        languages="English, Telugu, Hindi",
        consultation_types="IN_PERSON,VIDEO",
        appointment_duration=30,
        status=DoctorStatus.ACTIVE,
        external_provider_id="EXT-DOC-001"
    )
    doc_sharma = Doctor(
        hospital_id=hosp_abc.id,
        user_id=u_sharma.id,
        department_id=dept_gen.id,
        specialty_id=spec_gen.id,
        name="Dr. Priya Sharma",
        qualifications="MBBS, MD (General Medicine)",
        experience=9,
        languages="English, Hindi, Telugu",
        consultation_types="IN_PERSON,VIDEO",
        appointment_duration=30,
        status=DoctorStatus.ACTIVE,
        external_provider_id="EXT-DOC-002"
    )
    doc_kiran = Doctor(
        hospital_id=hosp_xyz.id,
        user_id=u_kiran.id,
        department_id=dept_derma.id,
        specialty_id=spec_derma.id,
        name="Dr. Kiran Kumar",
        qualifications="MBBS, MD (Dermatology, Venereology & Leprosy)",
        experience=11,
        languages="English, Telugu",
        consultation_types="IN_PERSON",
        appointment_duration=30,
        status=DoctorStatus.ACTIVE,
        external_provider_id="EXT-DOC-003"
    )
    doc_sunita = Doctor(
        hospital_id=hosp_xyz.id,
        user_id=u_sunita.id,
        department_id=dept_ped.id,
        specialty_id=spec_ped.id,
        name="Dr. Sunita Reddy",
        qualifications="MBBS, DCH, DNB (Pediatrics)",
        experience=7,
        languages="English, Telugu",
        consultation_types="IN_PERSON,VIDEO",
        appointment_duration=30,
        status=DoctorStatus.ACTIVE,
        external_provider_id="EXT-DOC-004"
    )
    db.add_all([doc_rao, doc_sharma, doc_kiran, doc_sunita])
    db.commit()

    # 6. Doctor Calendars & Availability
    for doc in [doc_rao, doc_sharma, doc_kiran, doc_sunita]:
        cal = Calendar(doctor_id=doc.id, name="Regular Outpatient Clinic", active=True)
        db.add(cal)
        db.commit()

        # Generate availability for today and the next 7 days
        today = datetime.utcnow()
        for i in range(8):
            day_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            # Morning window
            db.add(Availability(
                doctor_id=doc.id,
                calendar_id=cal.id,
                date=day_str,
                start_time="09:00",
                end_time="13:00",
                status=AvailabilityStatus.AVAILABLE
            ))
            # Afternoon window
            db.add(Availability(
                doctor_id=doc.id,
                calendar_id=cal.id,
                date=day_str,
                start_time="14:00",
                end_time="17:00",
                status=AvailabilityStatus.AVAILABLE
            ))
    db.commit()

    # Add a sample blocked slot for Dr. Rao (e.g. tomorrow at 12:00 - 13:00 for Surgery meeting)
    tomorrow_str = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    db.add(BlockedSlot(
        doctor_id=doc_rao.id,
        date=tomorrow_str,
        start_time="12:00",
        end_time="13:00",
        reason="Scheduled Hospital Surgical Review"
    ))
    db.commit()

    # 7. Patients
    u_ramesh = User(email="ramesh.varma@patient.org", hashed_password=hash_password("Patient@123"), role=Role.PATIENT)
    u_ananya = User(email="ananya.reddy@patient.org", hashed_password=hash_password("Patient@123"), role=Role.PATIENT)
    db.add_all([u_ramesh, u_ananya])
    db.commit()

    pat_ramesh = Patient(
        user_id=u_ramesh.id,
        name="Ramesh Varma",
        email="ramesh.varma@patient.org",
        phone="9848022338",
        date_of_birth="1988-04-12",
        communication_preference="voice_and_sms",
        external_patient_id="EXT-PAT-001"
    )
    pat_ananya = Patient(
        user_id=u_ananya.id,
        name="Ananya Reddy",
        email="ananya.reddy@patient.org",
        phone="9848033449",
        date_of_birth="1994-09-21",
        communication_preference="in_app",
        external_patient_id="EXT-PAT-002"
    )
    db.add_all([pat_ramesh, pat_ananya])
    db.commit()

    # 8. Pre-Visit Questionnaires
    q_ortho = Questionnaire(
        hospital_id=hosp_abc.id,
        specialty_id=spec_ortho.id,
        name="Orthopedic Pre-Visit Assessment",
        status=QuestionnaireStatus.ACTIVE
    )
    db.add(q_ortho)
    db.commit()

    questions = [
        QuestionnaireQuestion(questionnaire_id=q_ortho.id, question="What joint or body area is experiencing discomfort?", type=QuestionType.SHORT_TEXT, required=True, order=1),
        QuestionnaireQuestion(questionnaire_id=q_ortho.id, question="How long have you had this pain/discomfort?", type=QuestionType.SINGLE_CHOICE, options="Less than 1 week,1-4 weeks,1-6 months,Over 6 months", required=True, order=2),
        QuestionnaireQuestion(questionnaire_id=q_ortho.id, question="Rate your current pain level from 1 to 10", type=QuestionType.NUMERIC, required=True, order=3),
        QuestionnaireQuestion(questionnaire_id=q_ortho.id, question="Have you had any prior surgeries or fractures in this area?", type=QuestionType.YES_NO, required=True, order=4),
        QuestionnaireQuestion(questionnaire_id=q_ortho.id, question="Are you currently taking any regular pain relief medications?", type=QuestionType.SHORT_TEXT, required=False, order=5)
    ]
    db.add_all(questions)
    db.commit()

    # 9. Default Workflow
    wf = Workflow(
        hospital_id=hosp_abc.id,
        name="Standard Pre-Visit Intake & Triage Pipeline",
        trigger_event="APPOINTMENT_CONFIRMED",
        steps_definition=[
            {"step": 1, "action": "ASSIGN_QUESTIONNAIRE", "delay_sec": 0},
            {"step": 2, "action": "NOTIFY_PATIENT", "delay_sec": 0},
            {"step": 3, "action": "NOTIFY_DOCTOR", "delay_sec": 0}
        ],
        active=True
    )
    db.add(wf)
    db.commit()

    db.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
