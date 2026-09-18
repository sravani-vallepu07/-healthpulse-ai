"""
Telephony Integration Module (PRD §11 Compliance)
Provides pluggable telephony connector architecture:
- Abstract TelephonyConnector
- Concrete MockTelephonyConnector (simulating inbound calls, patient lookup by caller ID, speech-to-agent bridge, audio playback, call drops)
- TwiML generation for Twilio Voice & Media Streams compatibility
"""
import time
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.ai.context import get_or_create_conversation
from app.ai.agent import run_ai_agent
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)


class TelephonyConnector(ABC):
    """Abstract connector interface for telephony platforms (Twilio, Amazon Connect, Mock)."""

    @abstractmethod
    def initiate_inbound_call(
        self, caller_phone: str, db: Session, hospital_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Accepts an inbound phone call, looks up patient, and initializes call session."""
        pass

    @abstractmethod
    def process_audio_stream(
        self, call_id: str, speech_transcript: str, db: Session
    ) -> Dict[str, Any]:
        """Pipes speech transcription to run_ai_agent and returns synthesized speech response."""
        pass

    @abstractmethod
    def handle_call_disconnect(
        self, call_id: str, reason: str, db: Session
    ) -> Dict[str, Any]:
        """Handles call completion or abnormal disconnection/failure (PRD §11)."""
        pass

    @abstractmethod
    def get_call_session(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves current state of a call session."""
        pass


class MockTelephonyConnector(TelephonyConnector):
    """
    Mock Telephony Connector simulating an enterprise voice gateway (e.g. Twilio Voice).
    Simulates inbound caller identification, conversational turn handling via run_ai_agent,
    audio stream playback synthesis, and network drop / failure recovery.
    """

    def __init__(self):
        # In-memory store of call sessions: call_id -> call_dict
        self._calls: Dict[str, Dict[str, Any]] = {}

    def initiate_inbound_call(
        self, caller_phone: str, db: Session, hospital_id: Optional[int] = None
    ) -> Dict[str, Any]:
        clean_phone = "".join(filter(str.isdigit, caller_phone))
        if len(clean_phone) > 10:
            clean_phone = clean_phone[-10:]

        # Lookup patient by phone number
        patient = None
        if clean_phone:
            patient = db.query(Patient).filter(
                Patient.phone.like(f"%{clean_phone}%")
            ).first()

        patient_id = patient.id if patient else None
        patient_name = patient.name if patient else "Valued Caller"

        # If guest caller, fallback to first patient or seed patient
        if not patient_id:
            default_p = db.query(Patient).first()
            patient_id = default_p.id if default_p else 1

        call_id = f"CALL-{uuid.uuid4().hex[:10].upper()}"
        conversation = get_or_create_conversation(db, patient_id=patient_id, hospital_id=hospital_id)

        greeting = (
            f"Hello {patient_name}! Thank you for calling HealthPulse AI healthcare access network. "
            "I am your administrative voice scheduling assistant. How can I help you today?"
        )

        session_data = {
            "call_id": call_id,
            "caller_phone": caller_phone,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "conversation_id": conversation.id,
            "hospital_id": hospital_id or conversation.hospital_id,
            "status": "IN_PROGRESS",  # IN_PROGRESS, COMPLETED, FAILED, ESCALATED_TO_HUMAN
            "created_at": time.time(),
            "last_turn_at": time.time(),
            "turns_count": 0,
            "greeting": greeting,
            "transcript_history": [
                {"speaker": "AGENT", "text": greeting, "timestamp": time.time()}
            ],
            "failure_reason": None,
            "is_escalated": False
        }
        self._calls[call_id] = session_data

        log_audit_event(
            db=db,
            actor=f"TELEPHONY:{caller_phone}",
            role="PATIENT",
            event_type="TELEPHONY_INBOUND_CALL",
            resource_type="CALL_SESSION",
            resource_id=call_id,
            hospital_id=hospital_id or conversation.hospital_id,
            correlation_id=call_id,
            safe_metadata={"caller_phone": caller_phone, "patient_id": patient_id}
        )

        return {
            "call_id": call_id,
            "caller_phone": caller_phone,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "conversation_id": conversation.id,
            "status": "IN_PROGRESS",
            "greeting": greeting,
            "audio_url": f"/api/telephony/media/{call_id}/greeting.wav"
        }

    def process_audio_stream(
        self, call_id: str, speech_transcript: str, db: Session
    ) -> Dict[str, Any]:
        session = self._calls.get(call_id)
        if not session:
            raise KeyError(f"Call session {call_id} not found.")

        if session["status"] in ("COMPLETED", "FAILED"):
            raise ValueError(f"Call {call_id} has already ended with status {session['status']}.")

        session["transcript_history"].append({
            "speaker": "PATIENT",
            "text": speech_transcript,
            "timestamp": time.time()
        })
        session["turns_count"] += 1
        session["last_turn_at"] = time.time()

        # Pipe transcription into the identical run_ai_agent flow used by /ai/chat
        ai_res = run_ai_agent(
            db=db,
            patient_id=session["patient_id"],
            conversation_id=session["conversation_id"],
            message=speech_transcript,
            hospital_id=session.get("hospital_id"),
            correlation_id=f"VOICE-{call_id}-{session['turns_count']}"
        )

        session["transcript_history"].append({
            "speaker": "AGENT",
            "text": ai_res["reply"],
            "timestamp": time.time()
        })

        if ai_res.get("is_escalated"):
            session["status"] = "ESCALATED_TO_HUMAN"
            session["is_escalated"] = True

        log_audit_event(
            db=db,
            actor=f"TELEPHONY:{session['caller_phone']}",
            role="PATIENT",
            event_type="TELEPHONY_TURN_PROCESSED",
            resource_type="CALL_SESSION",
            resource_id=call_id,
            hospital_id=session.get("hospital_id"),
            correlation_id=ai_res["correlation_id"],
            safe_metadata={
                "intent": ai_res["intent"],
                "capabilities": ai_res["capabilities_called"],
                "is_escalated": ai_res["is_escalated"]
            }
        )

        return {
            "call_id": call_id,
            "turn_index": session["turns_count"],
            "speech_transcript": speech_transcript,
            "agent_reply": ai_res["reply"],
            "audio_url": f"/api/telephony/media/{call_id}/turn_{session['turns_count']}.wav",
            "intent": ai_res["intent"],
            "is_escalated": ai_res["is_escalated"],
            "status": session["status"],
            "slots_suggested": ai_res.get("slots_suggested", []),
            "appointment_data": ai_res.get("appointment_data")
        }

    def handle_call_disconnect(
        self, call_id: str, reason: str, db: Session
    ) -> Dict[str, Any]:
        """
        Handles call termination and call failure recovery (PRD §11: Call failure handling).
        """
        session = self._calls.get(call_id)
        if not session:
            raise KeyError(f"Call session {call_id} not found.")

        is_abnormal_failure = reason.upper() in (
            "NETWORK_DROP", "TIMEOUT", "CARRIER_FAILURE", "DROPPED_CALL", "SIP_GATEWAY_ERROR"
        )

        if is_abnormal_failure:
            session["status"] = "FAILED"
            session["failure_reason"] = reason
            event_type = "TELEPHONY_CALL_FAILURE"
        else:
            session["status"] = "COMPLETED"
            session["failure_reason"] = None
            event_type = "TELEPHONY_CALL_COMPLETED"

        session["disconnected_at"] = time.time()

        log_audit_event(
            db=db,
            actor=f"TELEPHONY:{session['caller_phone']}",
            role="PATIENT",
            event_type=event_type,
            resource_type="CALL_SESSION",
            resource_id=call_id,
            hospital_id=session.get("hospital_id"),
            correlation_id=call_id,
            safe_metadata={"disconnect_reason": reason, "status": session["status"]}
        )

        return {
            "call_id": call_id,
            "status": session["status"],
            "failure_reason": session["failure_reason"],
            "total_turns": session["turns_count"],
            "duration_seconds": round(session["disconnected_at"] - session["created_at"], 2),
            "transcript_summary": session["transcript_history"]
        }

    def get_call_session(self, call_id: str) -> Optional[Dict[str, Any]]:
        return self._calls.get(call_id)

    @staticmethod
    def generate_twiml(message: str, gather_action_url: Optional[str] = None) -> str:
        """Generates standard Twilio TwiML XML response for PSTN Voice integration."""
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="en-IN">{message}</Say>"""
        if gather_action_url:
            twiml += f"""
    <Gather input="speech" timeout="5" action="{gather_action_url}" method="POST">
        <Say voice="Polly.Aditi" language="en-IN">Please speak your response.</Say>
    </Gather>"""
        twiml += """
</Response>"""
        return twiml


# Singleton telephony connector instance
telephony_connector = MockTelephonyConnector()
