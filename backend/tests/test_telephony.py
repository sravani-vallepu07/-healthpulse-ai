"""
Telephony Integration & Voice Inbound Tests (PRD §11 Compliance)
Tests inbound call initiation, caller phone identification, speech-to-run_ai_agent bridge,
emergency symptom escalation, call failure handling, and Twilio webhook compatibility.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.patient import Patient
from app.integrations.telephony import telephony_connector

client = TestClient(app)

def test_telephony_inbound_patient_identification():
    """Telephony-1: Inbound call recognizes registered patient by phone number."""
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(Patient.email == "ramesh.varma@patient.org").first()
        assert patient is not None

        resp = client.post("/api/telephony/inbound", json={"caller_phone": "+91 9848022338"})
        assert resp.status_code == 200
        data = resp.json()
        assert "call_id" in data
        assert data["patient_id"] == patient.id
        assert "Ramesh Varma" in data["patient_name"]
        assert data["status"] == "IN_PROGRESS"
        assert "HealthPulse" in data["greeting"]
        assert data["audio_url"].endswith(".wav")
    finally:
        db.close()


def test_telephony_inbound_guest_caller():
    """Telephony-2: Inbound call from unknown number initializes safe guest session."""
    resp = client.post("/api/telephony/inbound", json={"caller_phone": "+91 9999900000"})
    assert resp.status_code == 200
    data = resp.json()
    assert "call_id" in data
    assert data["status"] == "IN_PROGRESS"
    assert "HealthPulse" in data["greeting"]


def test_telephony_voice_stream_turn():
    """Telephony-3: Streaming transcription executes run_ai_agent and returns voice reply."""
    # 1. Start call
    init_resp = client.post("/api/telephony/inbound", json={"caller_phone": "9848022338"})
    call_id = init_resp.json()["call_id"]

    # 2. Stream user speech turn
    stream_resp = client.post("/api/telephony/stream", json={
        "call_id": call_id,
        "speech_transcript": "I need an orthopedic specialist for my knee pain"
    })
    assert stream_resp.status_code == 200
    turn_data = stream_resp.json()
    assert turn_data["call_id"] == call_id
    assert turn_data["intent"] == "FIND_DOCTOR"
    assert "Dr. Anil Rao" in turn_data["agent_reply"]
    assert len(turn_data["slots_suggested"]) > 0
    assert turn_data["turn_index"] == 1
    assert turn_data["audio_url"].endswith(".wav")


def test_telephony_emergency_symptom_escalation():
    """Telephony-4: Emergency symptoms detected during call trigger human escalation."""
    init_resp = client.post("/api/telephony/inbound", json={"caller_phone": "9848022338"})
    call_id = init_resp.json()["call_id"]

    stream_resp = client.post("/api/telephony/stream", json={
        "call_id": call_id,
        "speech_transcript": "Help me, I am having acute chest pain and shortness of breath"
    })
    assert stream_resp.status_code == 200
    data = stream_resp.json()
    assert data["is_escalated"] is True
    assert data["status"] == "ESCALATED_TO_HUMAN"
    assert "emergency" in data["agent_reply"].lower() or "108" in data["agent_reply"]


def test_telephony_call_failure_handling():
    """Telephony-5: PRD §11 Call failure handling records abnormal disconnects for recovery."""
    init_resp = client.post("/api/telephony/inbound", json={"caller_phone": "9848022338"})
    call_id = init_resp.json()["call_id"]

    # Simulate network drop / carrier failure during call
    disc_resp = client.post("/api/telephony/disconnect", json={
        "call_id": call_id,
        "reason": "NETWORK_DROP"
    })
    assert disc_resp.status_code == 200
    disc_data = disc_resp.json()
    assert disc_data["status"] == "FAILED"
    assert disc_data["failure_reason"] == "NETWORK_DROP"

    # Verify session details
    get_resp = client.get(f"/api/telephony/calls/{call_id}")
    assert get_resp.status_code == 200
    session = get_resp.json()
    assert session["status"] == "FAILED"


def test_telephony_normal_call_completion():
    """Telephony-6: Normal call completion records transcript summary and duration."""
    init_resp = client.post("/api/telephony/inbound", json={"caller_phone": "9848022338"})
    call_id = init_resp.json()["call_id"]

    client.post("/api/telephony/stream", json={
        "call_id": call_id,
        "speech_transcript": "What hospitals are in Vijayawada?"
    })

    disc_resp = client.post("/api/telephony/disconnect", json={
        "call_id": call_id,
        "reason": "NORMAL_CLEARING"
    })
    assert disc_resp.status_code == 200
    disc_data = disc_resp.json()
    assert disc_data["status"] == "COMPLETED"
    assert disc_data["total_turns"] >= 1
    assert len(disc_data["transcript_summary"]) >= 2


def test_telephony_twilio_webhook_twiml_generation():
    """Telephony-7: Twilio voice webhook returns valid XML TwiML response."""
    resp = client.post(
        "/api/telephony/webhook/twilio",
        data={"From": "+919848022338", "CallSid": "TWILIO-TEST-12345"}
    )
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    assert "<Response>" in resp.text
    assert "<Say" in resp.text
    assert "HealthPulse" in resp.text
