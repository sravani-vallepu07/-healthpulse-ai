from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import User, Patient, Role
from app.schemas.schemas import UserRegister, UserLogin, Token, UserOut
from app.auth.security import hash_password, verify_password, create_access_token, require_current_user
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "EMAIL_EXISTS", "message": "Email is already registered"}
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        hospital_id=payload.hospital_id if payload.role != Role.PLATFORM_ADMIN else None,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # If patient, create patient record
    if payload.role == Role.PATIENT:
        patient = Patient(
            user_id=user.id,
            name=payload.name,
            email=payload.email,
            phone=payload.phone or "9999999999",
            date_of_birth=payload.date_of_birth,
            external_patient_id=f"EXT-PAT-{user.id}"
        )
        db.add(patient)
        db.commit()

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value, "hospital_id": user.hospital_id})

    log_audit_event(
        db=db,
        actor=user.email,
        role=user.role.value,
        event_type="USER_REGISTERED",
        resource_type="USER",
        resource_id=str(user.id),
        correlation_id=f"AUTH-{user.id}"
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        role=user.role.value,
        hospital_id=user.hospital_id,
        name=payload.name
    )

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}
        )

    name = user.email.split("@")[0].capitalize()
    if user.patient_profile:
        name = user.patient_profile.name
    elif user.doctor_profile:
        name = user.doctor_profile.name

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value, "hospital_id": user.hospital_id})

    log_audit_event(
        db=db,
        actor=user.email,
        role=user.role.value,
        event_type="USER_LOGIN",
        resource_type="USER",
        resource_id=str(user.id),
        correlation_id=f"LOGIN-{user.id}"
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        role=user.role.value,
        hospital_id=user.hospital_id,
        name=name
    )

@router.get("/me")
def get_current_user_profile(user: User = Depends(require_current_user)):
    name = user.email.split("@")[0].capitalize()
    patient_id = None
    doctor_id = None
    if user.patient_profile:
        name = user.patient_profile.name
        patient_id = user.patient_profile.id
    elif user.doctor_profile:
        name = user.doctor_profile.name
        doctor_id = user.doctor_profile.id

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "hospital_id": user.hospital_id,
        "name": name,
        "patient_id": patient_id,
        "doctor_id": doctor_id
    }
