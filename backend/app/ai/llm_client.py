import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pydantic import BaseModel
import httpx

from app.config import settings
from app.ai.prompts import LLM_NLU_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class ExtractedNLU(BaseModel):
    intent: str
    specialty: Optional[str] = None
    doctor_name: Optional[str] = None
    target_date: Optional[str] = None
    time_slot: Optional[str] = None
    clarification_question: Optional[str] = None
    confidence: float = 1.0

def parse_relative_date(text: str) -> str:
    lower = text.lower()
    today = datetime.now()
    if "tomorrow" in lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "friday" in lower:
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    if "wednesday" in lower:
        days_ahead = 2 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    if "monday" in lower:
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return today.strftime("%Y-%m-%d")

def parse_time_slot(text: str) -> Optional[str]:
    match = re.search(r"(\d{1,2}:\d{2})", text)
    if match:
        t = match.group(1)
        if len(t.split(":")[0]) == 1:
            t = f"0{t}"
        return t
    match_am_pm = re.search(r"(\d{1,2})\s*(am|pm)", text, re.IGNORECASE)
    if match_am_pm:
        hour = int(match_am_pm.group(1))
        period = match_am_pm.group(2).lower()
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:00"
    return None

def _deterministic_nlu_fallback(message: str, context: Dict[str, Any]) -> ExtractedNLU:
    """
    High-accuracy deterministic NLU parser implementing PRD §9/§10
    (Clarification over guessing, context retention, and slot extraction).
    """
    text = message.lower().strip()
    target_date = parse_relative_date(text)
    time_slot = parse_time_slot(text)
    
    # Check for doctor/specialty in text
    specialty = None
    if any(k in text for k in ["ortho", "joint", "bone", "knee", "spine", "fracture"]):
        specialty = "Orthopedics"
    elif any(k in text for k in ["derma", "skin", "rash", "acne", "hair"]):
        specialty = "Dermatology"
    elif any(k in text for k in ["general", "physician", "fever", "cough", "cold", "flu", "internal medicine"]):
        specialty = "General Medicine"
    elif any(k in text for k in ["pediatric", "child", "baby"]):
        specialty = "Pediatrics"
    
    doctor_name = None
    for name in ["Rao", "Priya", "Kiran", "Sunita", "Sharma"]:
        if name.lower() in text:
            doctor_name = name
            break

    # Cancellation
    if any(w in text for w in ["cancel", "drop my appointment", "stop my appointment", "delete booking"]):
        return ExtractedNLU(intent="CANCEL_APPOINTMENT", target_date=target_date, time_slot=time_slot)
    
    # Rescheduling
    if any(w in text for w in ["reschedule", "move my appointment", "change appointment time", "postpone", "different time", "different day"]):
        return ExtractedNLU(intent="RESCHEDULE_APPOINTMENT", target_date=target_date, time_slot=time_slot, doctor_name=doctor_name, specialty=specialty)
    
    # Questionnaire
    if any(w in text for w in ["questionnaire", "pre-visit", "intake form", "survey", "medical history form"]):
        return ExtractedNLU(intent="QUESTIONNAIRE")
    
    # Check Appointment
    if any(w in text for w in ["check appointment", "my appointments", "status of appointment", "upcoming appointment", "view booking"]):
        return ExtractedNLU(intent="CHECK_APPOINTMENT")
    
    # Hospital search
    if any(w in text for w in ["hospital", "clinic", "center", "centre", "facilities in", "approved hospitals"]):
        if not specialty and not doctor_name:
            return ExtractedNLU(intent="FIND_HOSPITAL")

    # Ambiguous booking requests without doctor, specialty, or slot (PRD §9/§10: Clarification over guessing)
    has_doctor_context = bool(context.get("selected_doctor_id")) or bool(doctor_name) or bool(specialty)
    is_ambiguous_booking = (
        any(w in text for w in ["book an appointment", "schedule an appointment", "schedule a visit", "book a visit", "i need an appointment", "want to book", "can you book"])
        and not time_slot
        and not has_doctor_context
    )
    if is_ambiguous_booking:
        return ExtractedNLU(
            intent="CLARIFICATION_NEEDED",
            specialty=None,
            doctor_name=None,
            target_date=target_date,
            time_slot=None,
            clarification_question="I would be pleased to help you book an appointment. Could you please specify which doctor, specialty (such as Orthopedics or Dermatology), or hospital you would like to visit?",
            confidence=0.9
        )

    # Time slot booking check
    is_time_requested = bool(time_slot) or any(w in text for w in ["book", "reserve", "schedule", "take slot", "confirm slot"])
    
    if is_time_requested and (time_slot or "book" in text or "reserve" in text or "schedule" in text):
        return ExtractedNLU(
            intent="BOOK_APPOINTMENT",
            specialty=specialty,
            doctor_name=doctor_name,
            target_date=target_date,
            time_slot=time_slot
        )
    
    # Doctor discovery or Contextual Date Shift ("Actually, make that Friday")
    if specialty or doctor_name or any(w in text for w in ["doctor", "specialist", "physician", "appointment", "bone", "joint", "skin", "fever"]) or any(w in text for w in ["friday", "tomorrow", "wednesday", "next week", "make that"]):
        return ExtractedNLU(
            intent="FIND_DOCTOR",
            specialty=specialty,
            doctor_name=doctor_name,
            target_date=target_date,
            time_slot=time_slot
        )
        
    return ExtractedNLU(intent="GENERAL_ADMINISTRATIVE_QUERY", target_date=target_date)

def call_anthropic_nlu(message: str, context: Dict[str, Any], api_key: str, model: str = "claude-3-5-sonnet-20241022") -> Optional[ExtractedNLU]:
    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        user_prompt = f"Patient Message: \"{message}\"\nCurrent Context: {json.dumps(context)}\nRespond with valid JSON adhering to the schema."
        payload = {
            "model": model,
            "max_tokens": 1024,
            "system": LLM_NLU_SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["content"][0]["text"].strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                parsed = json.loads(text.strip())
                return ExtractedNLU(**parsed)
    except Exception as e:
        logger.warning(f"Anthropic NLU call failed: {e}. Falling back to deterministic NLU.")
    return None

def call_openai_nlu(message: str, context: Dict[str, Any], api_key: str, model: str = "gpt-4o-mini") -> Optional[ExtractedNLU]:
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        user_prompt = f"Patient Message: \"{message}\"\nCurrent Context: {json.dumps(context)}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": LLM_NLU_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return ExtractedNLU(**parsed)
    except Exception as e:
        logger.warning(f"OpenAI NLU call failed: {e}. Falling back to deterministic NLU.")
    return None

def call_gemini_nlu(message: str, context: Dict[str, Any], api_key: str, model: str = "gemini-1.5-pro") -> Optional[ExtractedNLU]:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        user_prompt = f"{LLM_NLU_SYSTEM_PROMPT}\n\nPatient Message: \"{message}\"\nCurrent Context: {json.dumps(context)}\nOutput valid JSON:"
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.0}
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return ExtractedNLU(**parsed)
    except Exception as e:
        logger.warning(f"Gemini NLU call failed: {e}. Falling back to deterministic NLU.")
    return None

def extract_intent_and_slots(message: str, context: Dict[str, Any]) -> ExtractedNLU:
    """
    Primary NLU entry point: executes configured LLM provider when API key
    is available, with seamless, robust fallback to deterministic NLU.
    """
    provider = (settings.LLM_PROVIDER or "structured_agent").lower()
    api_key = settings.LLM_API_KEY or (
        settings.OPENAI_API_KEY if provider == "openai" else
        settings.ANTHROPIC_API_KEY if provider == "anthropic" else
        settings.GEMINI_API_KEY if provider in ["gemini", "google"] else None
    )
    
    if api_key:
        if provider == "openai":
            res = call_openai_nlu(message, context, api_key, model=settings.LLM_MODEL or "gpt-4o-mini")
            if res:
                return res
        elif provider == "anthropic":
            res = call_anthropic_nlu(message, context, api_key, model=settings.LLM_MODEL or "claude-3-5-sonnet-20241022")
            if res:
                return res
        elif provider in ["gemini", "google"]:
            res = call_gemini_nlu(message, context, api_key, model=settings.LLM_MODEL or "gemini-1.5-pro")
            if res:
                return res

    # Structured deterministic NLU fallback
    return _deterministic_nlu_fallback(message, context)
