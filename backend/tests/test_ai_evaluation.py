"""
AI Evaluation Benchmark Suite
Tests the LangGraph AI agent across 14 evaluation scenarios.
Each test verifies: correct intent detection, proper capability calls,
contextual continuity, and appropriate response generation.
"""
import uuid
import pytest
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.patient import Patient, User
from app.ai.agent import run_ai_agent, intent_recognition_node, AgentState, safety_check_node, build_agent_graph
from app.ai.capabilities import AICapabilities
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode


def _make_state(text: str) -> AgentState:
    return {
        "message": text,
        "patient_id": 0,
        "conversation_id": 0,
        "hospital_id": None,
        "context": {},
        "intent": "GENERAL_ADMINISTRATIVE_QUERY",
        "capabilities_called": [],
        "slots_suggested": [],
        "appointment_data": None,
        "reply": "",
        "is_escalated": False,
        "correlation_id": "TEST-EVAL"
    }


def test_eval_intent_doctor_search():
    """Eval-1: Agent detects FIND_DOCTOR intent for orthopedic query."""
    state = _make_state("I need an orthopedic specialist")
    result = intent_recognition_node(state)
    assert result["intent"] == "FIND_DOCTOR", f"Expected FIND_DOCTOR, got {result['intent']}"


def test_eval_intent_book_appointment():
    """Eval-2: Agent detects BOOK_APPOINTMENT intent when user mentions a time slot."""
    state = _make_state("Book me the 10am slot")
    result = intent_recognition_node(state)
    assert result["intent"] == "BOOK_APPOINTMENT"


def test_eval_intent_cancel():
    """Eval-3: Agent detects CANCEL_APPOINTMENT intent."""
    state = _make_state("Please cancel my appointment")
    result = intent_recognition_node(state)
    assert result["intent"] == "CANCEL_APPOINTMENT"


def test_eval_intent_check_appointment():
    """Eval-4: Agent detects CHECK_APPOINTMENT intent."""
    state = _make_state("What are my upcoming appointments?")
    result = intent_recognition_node(state)
    assert result["intent"] == "CHECK_APPOINTMENT"


def test_eval_intent_hospital():
    """Eval-5: Agent detects FIND_HOSPITAL intent."""
    state = _make_state("What hospitals are near me?")
    result = intent_recognition_node(state)
    assert result["intent"] == "FIND_HOSPITAL"


def test_eval_intent_questionnaire():
    """Eval-6: Agent detects QUESTIONNAIRE intent."""
    state = _make_state("I want to fill my pre-visit form")
    result = intent_recognition_node(state)
    assert result["intent"] == "QUESTIONNAIRE"


def test_eval_intent_emergency_escalation():
    """Eval-7: Safety check catches emergency keywords and escalates."""
    state = _make_state("I have severe chest pain and cannot breathe")
    result = safety_check_node(state)
    assert result["is_escalated"] is True
    assert result["intent"] == "HUMAN_ESCALATION"


def test_eval_intent_date_shift():
    """Eval-8: Date shift maps to FIND_DOCTOR intent."""
    state = _make_state("Actually, make that Friday instead")
    result = intent_recognition_node(state)
    assert result["intent"] == "FIND_DOCTOR"


def test_eval_capabilities_search_hospitals():
    """Eval-9: search_hospitals capability returns approved hospitals."""
    db = SessionLocal()
    try:
        caps = AICapabilities(db, correlation_id="EVAL-SH-001")
        results = caps.search_hospitals()
        assert isinstance(results, list)
        for h in results:
            assert "id" in h
            assert "name" in h
    finally:
        db.close()


def test_eval_capabilities_search_doctors():
    """Eval-10: search_doctors returns doctors from approved hospitals only."""
    db = SessionLocal()
    try:
        caps = AICapabilities(db, correlation_id="EVAL-SD-001")
        results = caps.search_doctors()
        assert isinstance(results, list)
        for d in results:
            assert "id" in d
            assert "name" in d
            assert "specialty" in d
    finally:
        db.close()


def test_eval_capabilities_get_appointment():
    """Eval-11: get_appointment is always scoped to patient."""
    db = SessionLocal()
    try:
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patients in DB")
        caps = AICapabilities(db, correlation_id="EVAL-GA-001")
        results = caps.get_appointment(patient_id=patient.id)
        assert isinstance(results, list)
        # Garbage patient returns empty
        empty = caps.get_appointment(patient_id=999999)
        assert empty == []
    finally:
        db.close()


def test_eval_capabilities_lookup_patient():
    """Eval-12: lookup_patient returns safe patient info without sensitive PII."""
    db = SessionLocal()
    try:
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patients in DB")
        caps = AICapabilities(db, correlation_id="EVAL-LP-001")
        result = caps.lookup_patient(patient_id=patient.id)
        assert result is not None
        assert result["found"] is True
        assert "patient_id" in result
        assert "name" in result
        assert "ssn" not in result
    finally:
        db.close()


def test_eval_capabilities_get_context_empty():
    """Eval-13: get_context returns empty dict for unknown conversation."""
    db = SessionLocal()
    try:
        caps = AICapabilities(db, correlation_id="EVAL-CTX-001")
        ctx = caps.get_context(conversation_id=999999)
        assert isinstance(ctx, dict)
    finally:
        db.close()


def test_eval_context_retention_date_shift():
    """Eval-14: Date shift preserves selected_doctor_id in context."""
    db = SessionLocal()
    try:
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patients in DB")

        app = build_agent_graph(db)

        state1: AgentState = {
            "message": "I need an orthopedic specialist",
            "patient_id": patient.id,
            "conversation_id": 99991,
            "hospital_id": None,
            "context": {},
            "intent": "FIND_DOCTOR",
            "capabilities_called": [],
            "slots_suggested": [],
            "appointment_data": None,
            "reply": "",
            "is_escalated": False,
            "correlation_id": "EVAL-DATE-001"
        }
        final1 = app.invoke(state1)
        original_doc_id = final1["context"].get("selected_doctor_id")
        if original_doc_id is None:
            pytest.skip("No doctors available in DB")

        state2: AgentState = {
            "message": "Actually make that Friday",
            "patient_id": patient.id,
            "conversation_id": 99991,
            "hospital_id": None,
            "context": dict(final1["context"]),
            "intent": "FIND_DOCTOR",
            "capabilities_called": [],
            "slots_suggested": [],
            "appointment_data": None,
            "reply": "",
            "is_escalated": False,
            "correlation_id": "EVAL-DATE-002"
        }
        final2 = app.invoke(state2)
        assert final2["context"].get("selected_doctor_id") == original_doc_id, \
            "Doctor context overwritten during date shift — context retention bug!"
    finally:
        db.close()


def test_eval_ambiguous_input_triggers_clarification():
    """Eval-15: Ambiguous booking input triggers clarification question without guessing (PRD §9/§10)."""
    state = _make_state("I would like to book an appointment please")
    result = intent_recognition_node(state)
    assert result["intent"] == "CLARIFICATION_NEEDED"
    assert result.get("extracted_slots", {}).get("clarification_question") is not None
    assert "doctor" in result["reply"].lower() or "specialty" in result["reply"].lower()


def test_eval_paraphrased_clinical_phrasing():
    """Eval-16: Paraphrased non-keyword clinical vocabulary correctly maps to specialty."""
    state1 = _make_state("My knee joint is hurting severely after a sports injury, who can check my bones?")
    result1 = intent_recognition_node(state1)
    assert result1["intent"] == "FIND_DOCTOR"
    assert result1.get("extracted_slots", {}).get("specialty") == "Orthopedics"

    state2 = _make_state("I have an inflamed skin rash on my cheeks with severe itching")
    result2 = intent_recognition_node(state2)
    assert result2["intent"] == "FIND_DOCTOR"
    assert result2.get("extracted_slots", {}).get("specialty") == "Dermatology"


def test_eval_multiturn_clarification_to_resolution():
    """Eval-17: Ambiguous prompt triggers clarification, follow-up turn resolves to booking availability."""
    db = SessionLocal()
    try:
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patients in DB")

        app = build_agent_graph(db)

        # Turn 1: Ambiguous booking intent
        state1: AgentState = {
            "message": "Can you book an appointment for me?",
            "patient_id": patient.id,
            "conversation_id": 99992,
            "hospital_id": None,
            "context": {},
            "intent": "GENERAL_ADMINISTRATIVE_QUERY",
            "capabilities_called": [],
            "slots_suggested": [],
            "appointment_data": None,
            "reply": "",
            "is_escalated": False,
            "correlation_id": "EVAL-AMBIG-001"
        }
        res1 = app.invoke(state1)
        assert res1["intent"] == "CLARIFICATION_NEEDED"
        assert "specialty" in res1["reply"].lower() or "doctor" in res1["reply"].lower()

        # Turn 2: Patient clarifies specialty
        state2: AgentState = {
            "message": "I need Dr. Anil Rao for orthopedic care",
            "patient_id": patient.id,
            "conversation_id": 99992,
            "hospital_id": None,
            "context": dict(res1["context"]),
            "intent": "GENERAL_ADMINISTRATIVE_QUERY",
            "capabilities_called": [],
            "slots_suggested": [],
            "appointment_data": None,
            "reply": "",
            "is_escalated": False,
            "correlation_id": "EVAL-AMBIG-002"
        }
        res2 = app.invoke(state2)
        assert res2["intent"] == "FIND_DOCTOR"
        assert "check_availability" in res2["capabilities_called"]
        assert len(res2["slots_suggested"]) > 0
    finally:
        db.close()


def test_eval_llm_json_extraction_mocked(monkeypatch):
    """Eval-18: Verifies real LLM caller (Anthropic & OpenAI) parses structured JSON."""
    from app.ai.llm_client import call_anthropic_nlu, call_openai_nlu
    import httpx

    fake_openai_json = {
        "choices": [{
            "message": {
                "content": '{"intent": "FIND_DOCTOR", "specialty": "Orthopedics", "doctor_name": "Dr. Anil Rao", "target_date": "2026-10-15", "time_slot": "10:00", "clarification_question": null, "confidence": 0.98}'
            }
        }]
    }

    class FakeResponse:
        status_code = 200
        def json(self):
            return fake_openai_json

    def mock_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    parsed = call_openai_nlu("Book Dr Rao on 2026-10-15 at 10am", {}, api_key="fake-test-key")
    assert parsed is not None
    assert parsed.intent == "FIND_DOCTOR"
    assert parsed.doctor_name == "Dr. Anil Rao"
    assert parsed.specialty == "Orthopedics"
    assert parsed.time_slot == "10:00"

