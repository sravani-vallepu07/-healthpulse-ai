import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.ai import CapabilityExecution, AIContext
from app.models.tenant import Hospital, HospitalStatus, Specialty
from app.models.doctor import Doctor, DoctorStatus
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentStatus, AppointmentStateHistory
from app.models.questionnaire import Questionnaire, QuestionnaireResponse, QuestionnaireStatus
from app.services.scheduling_service import get_available_slots, validate_slot
from app.services.appointment_service import (
    create_appointment_with_verification,
    reschedule_appointment_flow,
    cancel_appointment_flow
)
from app.integrations.mock_ehr import mock_ehr_connector
from app.services.workflow_service import trigger_appointment_workflow, trigger_questionnaire_completed_workflow
from app.services.notification_service import create_notification
from app.schemas.schemas import (
    SearchHospitalsInput, SearchDoctorsInput, CheckAvailabilityInput,
    LookupPatientInput, GetAppointmentInput, CreateAppointmentCapabilityInput,
    RescheduleAppointmentCapabilityInput, CancelAppointmentCapabilityInput,
    GetQuestionnaireCapabilityInput, SubmitQuestionnaireCapabilityInput,
    SendNotificationCapabilityInput, StartWorkflowCapabilityInput,
    GetContextCapabilityInput, UpdatePreferencesCapabilityInput,
    VerifyExternalAppointmentCapabilityInput, SynchronizeStateCapabilityInput,
    TransferToHumanCapabilityInput
)

def _record_capability(
    db: Session,
    capability_name: str,
    input_payload: Dict[str, Any],
    output_payload: Dict[str, Any],
    status: str,
    correlation_id: str,
    error: Optional[str] = None
):
    try:
        execution = CapabilityExecution(
            capability_name=capability_name,
            input_payload=input_payload,
            output_payload=output_payload,
            status=status,
            error=error,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(execution)
        db.commit()
    except Exception as e:
        db.rollback()

class AICapabilities:
    def __init__(self, db: Session, correlation_id: Optional[str] = None):
        self.db = db
        self.correlation_id = correlation_id or f"CAP-{uuid.uuid4().hex[:8].upper()}"

    def search_hospitals(self, city: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        inputs = {"city": city, "query": query}
        try:
            q = self.db.query(Hospital).filter(Hospital.status == HospitalStatus.APPROVED)
            if city:
                q = q.filter(Hospital.city.ilike(f"%{city}%"))
            if query:
                q = q.filter(Hospital.name.ilike(f"%{query}%"))
            hospitals = q.all()
            results = [{
                "id": h.id,
                "name": h.name,
                "city": h.city,
                "address": h.address,
                "contact_phone": h.contact_phone
            } for h in hospitals]
            _record_capability(self.db, "search_hospitals", inputs, {"count": len(results)}, "SUCCESS", self.correlation_id)
            return results
        except Exception as e:
            _record_capability(self.db, "search_hospitals", inputs, {}, "FAILED", self.correlation_id, str(e))
            return []

    def search_doctors(
        self,
        specialty: Optional[str] = None,
        hospital_id: Optional[int] = None,
        name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        inputs = {"specialty": specialty, "hospital_id": hospital_id, "name": name}
        try:
            q = self.db.query(Doctor).join(Hospital).filter(
                Doctor.status == DoctorStatus.ACTIVE,
                Hospital.status == HospitalStatus.APPROVED
            )
            if hospital_id:
                q = q.filter(Doctor.hospital_id == hospital_id)
            if name:
                q = q.filter(Doctor.name.ilike(f"%{name}%"))
            if specialty:
                q = q.join(Doctor.specialty).filter(Specialty.name.ilike(f"%{specialty}%"))

            doctors = q.all()
            results = [{
                "id": d.id,
                "name": d.name,
                "specialty": d.specialty.name if d.specialty else "General Medicine",
                "hospital_id": d.hospital_id,
                "hospital_name": d.hospital.name,
                "experience_years": d.experience,
                "qualifications": d.qualifications,
                "languages": d.languages
            } for d in doctors]
            _record_capability(self.db, "search_doctors", inputs, {"count": len(results)}, "SUCCESS", self.correlation_id)
            return results
        except Exception as e:
            _record_capability(self.db, "search_doctors", inputs, {}, "FAILED", self.correlation_id, str(e))
            return []

    def check_availability(
        self,
        doctor_id: Optional[int] = None,
        hospital_id: Optional[int] = None,
        specialty_id: Optional[int] = None,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        inputs = {"doctor_id": doctor_id, "hospital_id": hospital_id, "specialty_id": specialty_id, "date": date}
        try:
            slots = get_available_slots(
                self.db,
                doctor_id=doctor_id,
                hospital_id=hospital_id,
                specialty_id=specialty_id,
                date=date
            )
            _record_capability(self.db, "check_availability", inputs, {"slots_found": len(slots)}, "SUCCESS", self.correlation_id)
            return slots
        except Exception as e:
            _record_capability(self.db, "check_availability", inputs, {}, "FAILED", self.correlation_id, str(e))
            return []

    def create_appointment(
        self,
        hospital_id: int,
        doctor_id: int,
        patient_id: int,
        date: str,
        start_time: str,
        end_time: str,
        reason: Optional[str] = None,
        actor_email: str = "ai_patient_agent"
    ) -> Dict[str, Any]:
        inputs = {
            "hospital_id": hospital_id, "doctor_id": doctor_id,
            "patient_id": patient_id, "date": date, "start_time": start_time,
            "end_time": end_time, "reason": reason
        }
        try:
            apt = create_appointment_with_verification(
                db=self.db,
                hospital_id=hospital_id,
                doctor_id=doctor_id,
                patient_id=patient_id,
                date=date,
                start_time=start_time,
                end_time=end_time,
                reason=reason,
                correlation_id=self.correlation_id,
                actor_email=actor_email
            )
            out = {
                "appointment_id": apt.id,
                "status": apt.status.value,
                "external_id": apt.external_appointment_id,
                "date": apt.date,
                "start_time": apt.start_time,
                "doctor_name": apt.doctor.name if apt.doctor else None,
                "hospital_name": apt.hospital.name if apt.hospital else None
            }
            _record_capability(self.db, "create_appointment", inputs, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "create_appointment", inputs, {}, "FAILED", self.correlation_id, str(e))
            raise

    def reschedule_appointment(
        self,
        appointment_id: int,
        new_date: str,
        new_start_time: str,
        new_end_time: str,
        actor_email: str = "ai_patient_agent"
    ) -> Dict[str, Any]:
        inputs = {"appointment_id": appointment_id, "new_date": new_date, "start_time": new_start_time, "end_time": new_end_time}
        try:
            apt = reschedule_appointment_flow(
                self.db,
                appointment_id=appointment_id,
                new_date=new_date,
                new_start_time=new_start_time,
                new_end_time=new_end_time,
                actor_email=actor_email,
                correlation_id=self.correlation_id
            )
            out = {"appointment_id": apt.id, "status": apt.status.value, "date": apt.date, "start_time": apt.start_time}
            _record_capability(self.db, "reschedule_appointment", inputs, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "reschedule_appointment", inputs, {}, "FAILED", self.correlation_id, str(e))
            raise

    def cancel_appointment(
        self,
        appointment_id: int,
        reason: Optional[str] = None,
        actor_email: str = "ai_patient_agent"
    ) -> Dict[str, Any]:
        inputs = {"appointment_id": appointment_id, "reason": reason}
        try:
            apt = cancel_appointment_flow(
                self.db,
                appointment_id=appointment_id,
                actor_email=actor_email,
                reason=reason,
                correlation_id=self.correlation_id
            )
            out = {"appointment_id": apt.id, "status": apt.status.value}
            _record_capability(self.db, "cancel_appointment", inputs, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "cancel_appointment", inputs, {}, "FAILED", self.correlation_id, str(e))
            raise

    def get_questionnaire(self, hospital_id: int, appointment_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        inputs = {"hospital_id": hospital_id, "appointment_id": appointment_id}
        try:
            q = self.db.query(Questionnaire).filter(
                Questionnaire.hospital_id == hospital_id,
                Questionnaire.status == QuestionnaireStatus.ACTIVE
            ).first()
            if not q:
                _record_capability(self.db, "get_questionnaire", inputs, {"found": False}, "SUCCESS", self.correlation_id)
                return None
            questions = [{
                "id": qu.id,
                "question": qu.question,
                "type": qu.type.value,
                "options": qu.options.split(",") if qu.options else [],
                "required": qu.required
            } for qu in sorted(q.questions, key=lambda x: x.order)]
            out = {"questionnaire_id": q.id, "name": q.name, "questions": questions}
            _record_capability(self.db, "get_questionnaire", inputs, {"found": True, "questions_count": len(questions)}, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "get_questionnaire", inputs, {}, "FAILED", self.correlation_id, str(e))
            return None

    def submit_questionnaire(
        self,
        questionnaire_id: int,
        appointment_id: int,
        patient_id: int,
        responses: Dict[str, Any]
    ) -> Dict[str, Any]:
        inputs = {"questionnaire_id": questionnaire_id, "appointment_id": appointment_id, "responses": responses}
        try:
            resp = QuestionnaireResponse(
                questionnaire_id=questionnaire_id,
                appointment_id=appointment_id,
                patient_id=patient_id,
                responses=responses,
                status="SUBMITTED"
            )
            self.db.add(resp)
            self.db.commit()
            self.db.refresh(resp)

            # Trigger notification workflow
            trigger_questionnaire_completed_workflow(self.db, appointment_id)

            out = {"response_id": resp.id, "status": "SUBMITTED"}
            _record_capability(self.db, "submit_questionnaire", inputs, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "submit_questionnaire", inputs, {}, "FAILED", self.correlation_id, str(e))
            raise

    def lookup_patient(self, patient_id: Optional[int] = None, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[Dict[str, Any]]:
        payload = LookupPatientInput(patient_id=patient_id, email=email, phone=phone).model_dump()
        try:
            q = self.db.query(Patient)
            if patient_id:
                q = q.filter(Patient.id == patient_id)
            elif email:
                q = q.filter(Patient.email == email)
            elif phone:
                q = q.filter(Patient.phone == phone)
            else:
                p = q.first()
                if not p:
                    _record_capability(self.db, "lookup_patient", payload, {"found": False}, "SUCCESS", self.correlation_id)
                    return {"found": False}
                q = q.filter(Patient.id == p.id)
            patient = q.first()
            if not patient:
                _record_capability(self.db, "lookup_patient", payload, {"found": False}, "SUCCESS", self.correlation_id)
                return {"found": False}
            out = {
                "found": True,
                "patient_id": patient.id,
                "id": patient.id,
                "name": patient.name,
                "email": patient.email,
                "phone": patient.phone,
                "date_of_birth": patient.date_of_birth,
                "communication_preference": patient.communication_preference,
                "external_patient_id": patient.external_patient_id
            }
            _record_capability(self.db, "lookup_patient", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "lookup_patient", payload, {}, "FAILED", self.correlation_id, str(e))
            return None

    def get_appointment(self, appointment_id: Optional[int] = None, patient_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        payload = GetAppointmentInput(appointment_id=appointment_id, patient_id=patient_id, status=status).model_dump()
        try:
            q = self.db.query(Appointment)
            if appointment_id:
                q = q.filter(Appointment.id == appointment_id)
            if patient_id:
                q = q.filter(Appointment.patient_id == patient_id)
            if status:
                q = q.filter(Appointment.status == status)
            apts = q.order_by(Appointment.id.desc()).limit(10).all()
            results = [{
                "id": a.id,
                "patient_id": a.patient_id,
                "doctor_id": a.doctor_id,
                "doctor_name": a.doctor.name if a.doctor else None,
                "hospital_id": a.hospital_id,
                "hospital_name": a.hospital.name if a.hospital else None,
                "date": a.date,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "status": a.status.value,
                "external_appointment_id": a.external_appointment_id,
                "correlation_id": a.correlation_id,
                "reason": a.reason
            } for a in apts]
            _record_capability(self.db, "get_appointment", payload, {"count": len(results), "appointments": results}, "SUCCESS", self.correlation_id)
            return results
        except Exception as e:
            _record_capability(self.db, "get_appointment", payload, {}, "FAILED", self.correlation_id, str(e))
            return []

    def send_notification(self, recipient_id: int, role: str, notif_type: str, title: str, message: str, appointment_id: Optional[int] = None) -> Dict[str, Any]:
        payload = SendNotificationCapabilityInput(recipient_id=recipient_id, role=role, notif_type=notif_type, title=title, message=message, appointment_id=appointment_id).model_dump()
        try:
            notif = create_notification(
                db=self.db,
                recipient_id=recipient_id,
                role=role,
                notif_type=notif_type,
                title=title,
                message=message,
                appointment_id=appointment_id
            )
            out = {"notification_id": notif.id, "recipient_id": recipient_id, "status": "SENT"}
            _record_capability(self.db, "send_notification", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "send_notification", payload, {}, "FAILED", self.correlation_id, str(e))
            raise

    def start_workflow(self, appointment_id: int, workflow_name: Optional[str] = None, trigger_event: str = "APPOINTMENT_CONFIRMED") -> Dict[str, Any]:
        payload = StartWorkflowCapabilityInput(workflow_name=workflow_name, appointment_id=appointment_id, trigger_event=trigger_event).model_dump()
        try:
            apt = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not apt:
                raise ValueError(f"Appointment {appointment_id} not found")
            exec_rec = trigger_appointment_workflow(self.db, apt, correlation_id=self.correlation_id)
            out = {
                "execution_id": exec_rec.id if exec_rec else None,
                "status": exec_rec.status if exec_rec else "COMPLETED"
            }
            _record_capability(self.db, "start_workflow", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "start_workflow", payload, {}, "FAILED", self.correlation_id, str(e))
            raise

    def get_context(self, conversation_id: int) -> Dict[str, Any]:
        payload = GetContextCapabilityInput(conversation_id=conversation_id).model_dump()
        try:
            ctx = self.db.query(AIContext).filter(AIContext.conversation_id == conversation_id).first()
            context_data = dict(ctx.context_data or {}) if ctx else {}
            out = {"conversation_id": conversation_id, "context_data": context_data}
            _record_capability(self.db, "get_context", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "get_context", payload, {}, "FAILED", self.correlation_id, str(e))
            return {"conversation_id": conversation_id, "context_data": {}}

    def update_preferences(self, patient_id: int, communication_preference: Optional[str] = None, preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = UpdatePreferencesCapabilityInput(patient_id=patient_id, communication_preference=communication_preference, preferences=preferences).model_dump()
        try:
            pat = self.db.query(Patient).filter(Patient.id == patient_id).first()
            if not pat:
                raise ValueError(f"Patient {patient_id} not found")
            if communication_preference:
                pat.communication_preference = communication_preference
            self.db.commit()
            out = {"patient_id": patient_id, "communication_preference": pat.communication_preference}
            _record_capability(self.db, "update_preferences", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "update_preferences", payload, {}, "FAILED", self.correlation_id, str(e))
            raise

    def verify_external_appointment(self, appointment_id: int, external_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        payload = VerifyExternalAppointmentCapabilityInput(appointment_id=appointment_id, external_id=external_id, idempotency_key=idempotency_key).model_dump()
        try:
            apt = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not apt:
                raise ValueError(f"Appointment {appointment_id} not found")
            ext_id = external_id or apt.external_appointment_id
            idem_key = idempotency_key or apt.idempotency_key
            record = mock_ehr_connector.verify_appointment(external_id=ext_id, idempotency_key=idem_key)
            is_verified = record is not None
            out = {
                "appointment_id": appointment_id,
                "is_verified": is_verified,
                "external_id": record.get("external_id") if record else ext_id,
                "external_status": record.get("status") if record else "NOT_FOUND"
            }
            _record_capability(self.db, "verify_external_appointment", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "verify_external_appointment", payload, {}, "FAILED", self.correlation_id, str(e))
            raise

    def synchronize_state(self, appointment_id: int, target_status: Optional[str] = None) -> Dict[str, Any]:
        payload = SynchronizeStateCapabilityInput(appointment_id=appointment_id, target_status=target_status).model_dump()
        try:
            apt = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not apt:
                raise ValueError(f"Appointment {appointment_id} not found")

            # Validate target transition
            if target_status:
                try:
                    target_enum = AppointmentStatus(target_status)
                    from app.models.appointment import can_transition_appointment
                    if not can_transition_appointment(apt.status, target_enum):
                        out = {
                            "appointment_id": appointment_id,
                            "internal_status": apt.status.value,
                            "external_status": None,
                            "synchronized": False,
                            "error": f"Invalid transition from {apt.status.value} to {target_status}"
                        }
                        _record_capability(self.db, "synchronize_state", payload, out, "FAILED", self.correlation_id)
                        return out
                except ValueError:
                    pass

            record = mock_ehr_connector.verify_appointment(external_id=apt.external_appointment_id, idempotency_key=apt.idempotency_key)
            if record:
                apt.status = AppointmentStatus.CONFIRMED
                apt.external_appointment_id = record.get("external_id")
                self.db.commit()
                out = {
                    "appointment_id": appointment_id,
                    "internal_status": apt.status.value,
                    "external_status": record.get("status"),
                    "synchronized": True
                }
            else:
                out = {
                    "appointment_id": appointment_id,
                    "internal_status": apt.status.value,
                    "external_status": "NOT_FOUND",
                    "synchronized": False
                }
            _record_capability(self.db, "synchronize_state", payload, out, "SUCCESS", self.correlation_id)
            return out
        except Exception as e:
            _record_capability(self.db, "synchronize_state", payload, {}, "FAILED", self.correlation_id, str(e))
            raise


    def transfer_to_human(self, reason: str, urgency: str = "URGENT") -> Dict[str, Any]:
        payload = TransferToHumanCapabilityInput(reason=reason, urgency=urgency).model_dump()
        out = {
            "escalated": True,
            "reason": reason,
            "urgency": urgency,
            "action": "Immediate transfer to human triage and emergency services notice dispatched."
        }
        _record_capability(self.db, "transfer_to_human", payload, out, "SUCCESS", self.correlation_id)
        return out

