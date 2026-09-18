from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.tenant import HospitalStatus
from app.models.patient import Role
from app.models.doctor import DoctorStatus, AvailabilityStatus
from app.models.appointment import AppointmentStatus
from app.models.questionnaire import QuestionType, QuestionnaireStatus, ResponseStatus

# Standard Error & Response
class StandardResponse(BaseModel):
    success: bool = True
    message: str = "Operation successful"
    correlation_id: Optional[str] = None
    data: Optional[Any] = None

class StandardError(BaseModel):
    success: bool = False
    error_code: str
    message: str
    correlation_id: Optional[str] = None

# Auth Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: Role = Role.PATIENT
    hospital_id: Optional[int] = None
    name: str
    phone: Optional[str] = "9999999999"
    date_of_birth: Optional[str] = "1990-01-01"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    hospital_id: Optional[int] = None
    name: str

class UserOut(BaseModel):
    id: int
    email: str
    role: Role
    hospital_id: Optional[int]
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Tenant Schemas
class HospitalCreate(BaseModel):
    name: str
    address: str
    city: str = "Vijayawada"
    contact_phone: str
    contact_email: str

class HospitalUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    status: Optional[HospitalStatus] = None

class HospitalOut(BaseModel):
    id: int
    name: str
    address: str
    city: str
    contact_phone: str
    contact_email: str
    status: HospitalStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None

class DepartmentOut(BaseModel):
    id: int
    hospital_id: int
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class SpecialtyCreate(BaseModel):
    name: str
    description: Optional[str] = None

class SpecialtyOut(BaseModel):
    id: int
    hospital_id: int
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Doctor Schemas
class DoctorCreate(BaseModel):
    hospital_id: int
    department_id: Optional[int] = None
    specialty_id: Optional[int] = None
    name: str
    qualifications: str = "MBBS, MD"
    experience: int = 5
    languages: str = "English, Telugu"
    consultation_types: str = "IN_PERSON,VIDEO"
    appointment_duration: int = 30
    status: DoctorStatus = DoctorStatus.ACTIVE

class DoctorUpdate(BaseModel):
    department_id: Optional[int] = None
    specialty_id: Optional[int] = None
    name: Optional[str] = None
    qualifications: Optional[str] = None
    experience: Optional[int] = None
    languages: Optional[str] = None
    consultation_types: Optional[str] = None
    appointment_duration: Optional[int] = None
    status: Optional[DoctorStatus] = None

class DoctorOut(BaseModel):
    id: int
    hospital_id: int
    department_id: Optional[int] = None
    specialty_id: Optional[int] = None
    name: str
    photo: Optional[str] = None
    qualifications: str
    experience: int
    languages: str
    consultation_types: str
    appointment_duration: int
    external_provider_id: Optional[str] = None
    status: DoctorStatus
    hospital_name: Optional[str] = None
    specialty_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Scheduling & Slot Schemas
class SlotQuery(BaseModel):
    doctor_id: Optional[int] = None
    hospital_id: Optional[int] = None
    specialty_id: Optional[int] = None
    date: Optional[str] = None # YYYY-MM-DD

class SlotOut(BaseModel):
    doctor_id: int
    doctor_name: str
    specialty: str
    hospital_id: int
    hospital_name: str
    date: str
    start_time: str
    end_time: str
    duration_minutes: int
    status: str = "AVAILABLE"

class AvailabilityCreate(BaseModel):
    doctor_id: int
    calendar_id: int
    date: str
    start_time: str
    end_time: str

class BlockedSlotCreate(BaseModel):
    doctor_id: int
    date: str
    start_time: str
    end_time: str
    reason: str = "Doctor unavailable"

# Appointment Schemas
class AppointmentCreate(BaseModel):
    hospital_id: int
    doctor_id: int
    patient_id: Optional[int] = None # Filled from auth or provided
    appointment_type: str = "IN_PERSON"
    date: str
    start_time: str
    end_time: str
    reason: Optional[str] = "Routine consultation"
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None

class AppointmentReschedule(BaseModel):
    date: str
    start_time: str
    end_time: str
    correlation_id: Optional[str] = None

class AppointmentCancel(BaseModel):
    reason: Optional[str] = "Patient requested cancellation"
    correlation_id: Optional[str] = None

class AppointmentOut(BaseModel):
    id: int
    hospital_id: int
    hospital_name: Optional[str] = None
    doctor_id: int
    doctor_name: Optional[str] = None
    specialty: Optional[str] = None
    patient_id: int
    patient_name: Optional[str] = None
    appointment_type: str
    date: str
    start_time: str
    end_time: str
    status: AppointmentStatus
    external_appointment_id: Optional[str] = None
    correlation_id: str
    idempotency_key: str
    reason: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Questionnaire Schemas
class QuestionCreate(BaseModel):
    question: str
    type: QuestionType = QuestionType.SHORT_TEXT
    options: Optional[str] = None
    required: bool = True
    order: int = 1

class QuestionnaireCreate(BaseModel):
    hospital_id: int
    doctor_id: Optional[int] = None
    specialty_id: Optional[int] = None
    appointment_type: Optional[str] = None
    name: str
    questions: List[QuestionCreate]

class QuestionnaireResponseCreate(BaseModel):
    appointment_id: int
    responses: Dict[str, Any]

# AI Assistant Schemas
class AIChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str
    patient_id: Optional[int] = None
    hospital_id: Optional[int] = None
    correlation_id: Optional[str] = None

class AIChatResponse(BaseModel):
    conversation_id: int
    reply: str
    intent: str
    capabilities_called: List[str] = []
    slots_suggested: List[Dict[str, Any]] = []
    appointment_data: Optional[Dict[str, Any]] = None
    correlation_id: str
    is_escalated: bool = False

class AIVoiceRequest(BaseModel):
    conversation_id: Optional[int] = None
    transcript: str
    patient_id: Optional[int] = None
    correlation_id: Optional[str] = None

# Integrations & Failure Simulation
class FailureModeUpdate(BaseModel):
    failure_mode: str # NONE, TIMEOUT, NETWORK_ERROR, AUTH_ERROR, VALIDATION_ERROR, SLOT_CONFLICT
    delay_seconds: float = 0.0

class OperationOut(BaseModel):
    id: int
    operation_type: str
    external_system: str
    status: str
    request_id: Optional[str]
    correlation_id: str
    retry_count: int
    error: Optional[str]
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class AuditEventOut(BaseModel):
    id: int
    actor: str
    role: str
    event_type: str
    resource_type: str
    resource_id: Optional[str]
    hospital_id: Optional[int]
    correlation_id: str
    safe_metadata: Optional[Dict[str, Any]]
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class NotificationOut(BaseModel):
    id: int
    recipient_id: int
    role: str
    type: str
    title: str
    message: str
    status: str
    appointment_id: Optional[int]
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# =============================================================
# Explicit AI Controlled Capability Schemas (§3)
# =============================================================
class SearchHospitalsInput(BaseModel):
    city: Optional[str] = None
    query: Optional[str] = None

class SearchDoctorsInput(BaseModel):
    specialty: Optional[str] = None
    hospital_id: Optional[int] = None
    name: Optional[str] = None

class CheckAvailabilityInput(BaseModel):
    doctor_id: Optional[int] = None
    hospital_id: Optional[int] = None
    specialty_id: Optional[int] = None
    date: Optional[str] = None

class LookupPatientInput(BaseModel):
    patient_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class GetAppointmentInput(BaseModel):
    appointment_id: Optional[int] = None
    patient_id: Optional[int] = None
    status: Optional[str] = None

class CreateAppointmentCapabilityInput(BaseModel):
    hospital_id: int
    doctor_id: int
    patient_id: int
    date: str
    start_time: str
    end_time: str
    appointment_type: str = "IN_PERSON"
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None

class RescheduleAppointmentCapabilityInput(BaseModel):
    appointment_id: int
    new_date: str
    new_start_time: str
    new_end_time: str
    reason: Optional[str] = None

class CancelAppointmentCapabilityInput(BaseModel):
    appointment_id: int
    reason: Optional[str] = None

class GetQuestionnaireCapabilityInput(BaseModel):
    hospital_id: int
    specialty_id: Optional[int] = None
    appointment_id: Optional[int] = None

class SubmitQuestionnaireCapabilityInput(BaseModel):
    questionnaire_id: int
    appointment_id: int
    patient_id: int
    responses: Dict[str, Any]

class SendNotificationCapabilityInput(BaseModel):
    recipient_id: int
    role: str
    notif_type: str
    title: str
    message: str
    appointment_id: Optional[int] = None

class StartWorkflowCapabilityInput(BaseModel):
    workflow_name: Optional[str] = None
    appointment_id: int
    trigger_event: str = "APPOINTMENT_CONFIRMED"

class GetContextCapabilityInput(BaseModel):
    conversation_id: int

class UpdatePreferencesCapabilityInput(BaseModel):
    patient_id: int
    communication_preference: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class VerifyExternalAppointmentCapabilityInput(BaseModel):
    appointment_id: int
    external_id: Optional[str] = None
    idempotency_key: Optional[str] = None

class SynchronizeStateCapabilityInput(BaseModel):
    appointment_id: int
    target_status: Optional[str] = None

class TransferToHumanCapabilityInput(BaseModel):
    reason: str
    urgency: str = "URGENT"

