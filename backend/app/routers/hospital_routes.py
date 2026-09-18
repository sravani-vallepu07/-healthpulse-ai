from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import Hospital, HospitalStatus, Department, Specialty
from app.models.patient import User, Role
from app.schemas.schemas import HospitalCreate, HospitalUpdate, HospitalOut, DepartmentCreate, DepartmentOut, SpecialtyCreate, SpecialtyOut
from app.auth.security import require_current_user, require_roles, verify_tenant_access
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])

@router.post("", response_model=HospitalOut)
def create_hospital(
    payload: HospitalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    # Default to SUBMITTED if created by hospital admin, or APPROVED if platform admin
    initial_status = HospitalStatus.APPROVED if user.role == Role.PLATFORM_ADMIN else HospitalStatus.SUBMITTED
    hospital = Hospital(
        name=payload.name,
        address=payload.address,
        city=payload.city,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        status=initial_status
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    log_audit_event(
        db=db,
        actor=user.email,
        role=user.role.value,
        event_type="HOSPITAL_CREATED",
        resource_type="HOSPITAL",
        resource_id=str(hospital.id),
        hospital_id=hospital.id,
        correlation_id=f"HOSP-{hospital.id}"
    )

    return hospital

@router.get("", response_model=List[HospitalOut])
def list_hospitals(
    status_filter: Optional[str] = None,
    city: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Hospital)
    if status_filter:
        q = q.filter(Hospital.status == status_filter)
    if city:
        q = q.filter(Hospital.city.ilike(f"%{city}%"))
    return q.all()

@router.get("/{hospital_id}", response_model=HospitalOut)
def get_hospital(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Hospital not found"})
    return hospital

@router.put("/{hospital_id}", response_model=HospitalOut)
def update_hospital(
    hospital_id: int,
    payload: HospitalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Hospital not found"})

    # Check tenant access
    verify_tenant_access(user, hospital_id)

    # Only platform admin can approve/reject/suspend status
    if payload.status and user.role != Role.PLATFORM_ADMIN and payload.status != hospital.status:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "FORBIDDEN", "message": "Only Platform Admin can change hospital lifecycle status"}
        )

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(hospital, field, value)

    db.commit()
    db.refresh(hospital)

    log_audit_event(
        db=db,
        actor=user.email,
        role=user.role.value,
        event_type="HOSPITAL_UPDATED",
        resource_type="HOSPITAL",
        resource_id=str(hospital.id),
        hospital_id=hospital.id,
        correlation_id=f"HOSP-UPD-{hospital.id}",
        safe_metadata={"status": hospital.status.value}
    )

    return hospital

# Departments
@router.post("/{hospital_id}/departments", response_model=DepartmentOut)
def add_department(
    hospital_id: int,
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    verify_tenant_access(user, hospital_id)
    dept = Department(hospital_id=hospital_id, name=payload.name, description=payload.description)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

@router.get("/{hospital_id}/departments", response_model=List[DepartmentOut])
def get_departments(hospital_id: int, db: Session = Depends(get_db)):
    return db.query(Department).filter(Department.hospital_id == hospital_id).all()

# Specialties
@router.post("/{hospital_id}/specialties", response_model=SpecialtyOut)
def add_specialty(
    hospital_id: int,
    payload: SpecialtyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([Role.PLATFORM_ADMIN, Role.HOSPITAL_ADMIN]))
):
    verify_tenant_access(user, hospital_id)
    spec = Specialty(hospital_id=hospital_id, name=payload.name, description=payload.description)
    db.add(spec)
    db.commit()
    db.refresh(spec)
    return spec

@router.get("/{hospital_id}/specialties", response_model=List[SpecialtyOut])
def get_specialties(hospital_id: int, db: Session = Depends(get_db)):
    return db.query(Specialty).filter(Specialty.hospital_id == hospital_id).all()
