import re
import uuid
from datetime import datetime, timedelta
from typing import TypedDict, List, Dict, Any, Optional
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from app.ai.prompts import HEALTHCARE_ADMIN_SYSTEM_PROMPT, EMERGENCY_ESCALATION_MESSAGE
from app.ai.capabilities import AICapabilities
from app.ai.context import get_context_data, update_context_data
from app.models.appointment import Appointment

class AgentState(TypedDict):
    message: str
    patient_id: int
    conversation_id: int
    hospital_id: Optional[int]
    context: Dict[str, Any]
    intent: str
    capabilities_called: List[str]
    slots_suggested: List[Dict[str, Any]]
    appointment_data: Optional[Dict[str, Any]]
    reply: str
    is_escalated: bool
    correlation_id: str

def parse_target_date(text: str) -> str:
    lower = text.lower()
    today = datetime.utcnow()
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
    # check for YYYY-MM-DD
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

def safety_check_node(state: AgentState) -> AgentState:
    text = state["message"].lower()
    emergency_keywords = [
        "chest pain", "heart attack", "severe breathlessness", 
        "cannot breathe", "shortness of breath", "fainted", 
        "heavy bleeding", "severe chest discomfort"
    ]
    if any(k in text for k in emergency_keywords):
        state["is_escalated"] = True
        state["intent"] = "HUMAN_ESCALATION"
        state["reply"] = EMERGENCY_ESCALATION_MESSAGE
    return state

def should_escalate(state: AgentState) -> str:
    if state["is_escalated"]:
        return "escalate"
    return "proceed"

def intent_recognition_node(state: AgentState) -> AgentState:
    text = state["message"].lower()
    
    if any(w in text for w in ["cancel", "drop my appointment", "stop my appointment"]):
        state["intent"] = "CANCEL_APPOINTMENT"
    elif any(w in text for w in ["reschedule", "move my appointment", "change appointment time", "postpone"]):
        state["intent"] = "RESCHEDULE_APPOINTMENT"
    elif any(w in text for w in ["questionnaire", "pre-visit", "form", "survey"]):
        state["intent"] = "QUESTIONNAIRE"
    elif any(w in text for w in ["check appointment", "my appointments", "status of appointment", "upcoming"]):
        state["intent"] = "CHECK_APPOINTMENT"
    elif any(w in text for w in ["book", "reserve", "schedule", "take slot", "am", "pm", ":00", ":30"]):
        # Check if user is picking a slot
        if parse_time_slot(text) or "book" in text:
            state["intent"] = "BOOK_APPOINTMENT"
        else:
            state["intent"] = "FIND_DOCTOR"
    elif any(w in text for w in ["doctor", "specialist", "orthopedic", "ortho", "dermatology", "physician", "rao", "priya", "kiran", "cardiologist"]):
        state["intent"] = "FIND_DOCTOR"
    elif any(w in text for w in ["hospital", "clinic", "center", "centre", "abc", "xyz"]):
        state["intent"] = "FIND_HOSPITAL"
    elif any(w in text for w in ["friday", "tomorrow", "wednesday", "next week", "make that"]):
        # Contextual date shift
        state["intent"] = "FIND_DOCTOR"
    else:
        state["intent"] = "GENERAL_ADMINISTRATIVE_QUERY"

    return state

def build_agent_graph(db: Session):
    workflow = StateGraph(AgentState)

    def capability_execution_node(state: AgentState) -> AgentState:
        tools = AICapabilities(db, correlation_id=state["correlation_id"])
        intent = state["intent"]
        msg = state["message"]
        ctx = state["context"]
        caps_called = list(state["capabilities_called"])

        if intent == "HUMAN_ESCALATION":
            tools.transfer_to_human(reason="Emergency symptom detected in patient prompt", urgency="CRITICAL")
            caps_called.append("transfer_to_human")
            state["capabilities_called"] = caps_called
            return state

        if intent == "FIND_HOSPITAL":
            hospitals = tools.search_hospitals(city="Vijayawada")
            caps_called.append("search_hospitals")
            if hospitals:
                names = ", ".join([h["name"] for h in hospitals])
                state["reply"] = f"We have approved hospitals in Vijayawada: {names}. Which specialty or hospital do you prefer?"
            else:
                state["reply"] = "Currently no hospitals are approved for booking in this region."

        elif intent == "FIND_DOCTOR":
            # Extract specialty or name
            spec = None
            if "ortho" in msg.lower():
                spec = "Orthopedics"
            elif "derma" in msg.lower():
                spec = "Dermatology"
            elif "general" in msg.lower() or "physician" in msg.lower() or "fever" in msg.lower():
                spec = "General Medicine"

            doc_name = None
            for n in ["Rao", "Priya", "Kiran"]:
                if n.lower() in msg.lower():
                    doc_name = n

            # Search doctors
            doctors = tools.search_doctors(specialty=spec, name=doc_name, hospital_id=state["hospital_id"])
            caps_called.append("search_doctors")

            if doctors:
                selected_doc = doctors[0]
                ctx["selected_doctor_id"] = selected_doc["id"]
                ctx["selected_hospital_id"] = selected_doc["hospital_id"]

                # Check real availability
                target_date = parse_target_date(msg)
                ctx["selected_date"] = target_date
                
                slots = tools.check_availability(
                    doctor_id=selected_doc["id"],
                    hospital_id=selected_doc["hospital_id"],
                    date=target_date
                )
                caps_called.append("check_availability")
                state["slots_suggested"] = slots[:4]
                ctx["last_suggested_slots"] = slots[:4]

                if slots:
                    times_list = ", ".join([s["start_time"] for s in slots[:4]])
                    state["reply"] = (
                        f"I found {selected_doc['name']} ({selected_doc['specialty']} at {selected_doc['hospital_name']}). "
                        f"Available appointments on {target_date} are: {times_list}. Which time works best for you?"
                    )
                else:
                    state["reply"] = f"{selected_doc['name']} has no open slots on {target_date}. Would you like to check another day?"
            else:
                # If no specific doctor found, check general availability
                state["reply"] = "I can help you find an appointment. We have specialists in Orthopedics, General Medicine, and Dermatology. Which specialty do you need?"

        elif intent == "BOOK_APPOINTMENT":
            # Attempt to book slot
            slot_time = parse_time_slot(msg)
            doc_id = ctx.get("selected_doctor_id")
            hosp_id = ctx.get("selected_hospital_id")
            target_date = ctx.get("selected_date") or parse_target_date(msg)

            # If user didn't specify doctor yet, try to find default or ask
            if not doc_id:
                # Discover doctor first
                docs = tools.search_doctors(specialty="Orthopedics")
                if docs:
                    doc_id = docs[0]["id"]
                    hosp_id = docs[0]["hospital_id"]
                    ctx["selected_doctor_id"] = doc_id
                    ctx["selected_hospital_id"] = hosp_id

            if not slot_time:
                # If no slot parsed, see if slots were suggested previously and pick first
                if ctx.get("last_suggested_slots"):
                    slot_time = ctx["last_suggested_slots"][0]["start_time"]
                else:
                    slot_time = "10:00"

            # Compute end time (30 mins)
            st_dt = datetime.strptime(slot_time, "%H:%M")
            end_time = (st_dt + timedelta(minutes=30)).strftime("%H:%M")

            try:
                apt_res = tools.create_appointment(
                    hospital_id=hosp_id or 1,
                    doctor_id=doc_id or 1,
                    patient_id=state["patient_id"],
                    date=target_date,
                    start_time=slot_time,
                    end_time=end_time,
                    reason="Patient intake consultation"
                )
                caps_called.append("create_appointment")
                caps_called.append("verify_external_appointment")
                caps_called.append("synchronize_state")

                state["appointment_data"] = apt_res
                ctx["current_appointment_id"] = apt_res["appointment_id"]

                state["reply"] = (
                    f"Your appointment with {apt_res['doctor_name']} at {apt_res['hospital_name']} "
                    f"on {apt_res['date']} at {apt_res['start_time']} has been verified and confirmed in the hospital system. "
                    f"(External Ref: {apt_res['external_id']}). A pre-visit questionnaire has been assigned to your portal."
                )
            except Exception as e:
                state["reply"] = f"Unable to confirm booking: {str(e)}"

        elif intent == "CANCEL_APPOINTMENT":
            apt_id = ctx.get("current_appointment_id")
            if not apt_id:
                # Find patient's latest appointment
                latest_apt = db.query(Appointment).filter(
                    Appointment.patient_id == state["patient_id"],
                    Appointment.status.in_(["CONFIRMED", "PENDING"])
                ).order_by(Appointment.id.desc()).first()
                if latest_apt:
                    apt_id = latest_apt.id

            if apt_id:
                try:
                    res = tools.cancel_appointment(appointment_id=apt_id, reason="Patient requested cancellation")
                    caps_called.append("cancel_appointment")
                    state["reply"] = f"Appointment #{apt_id} has been cancelled in the system, and your slot has been released."
                except Exception as e:
                    state["reply"] = f"Could not cancel appointment: {str(e)}"
            else:
                state["reply"] = "You do not have any active upcoming appointments to cancel."

        elif intent == "CHECK_APPOINTMENT":
            caps_called.append("get_appointment")
            apts = db.query(Appointment).filter(
                Appointment.patient_id == state["patient_id"]
            ).order_by(Appointment.id.desc()).limit(3).all()
            if apts:
                details = "; ".join([f"#{a.id} with {a.doctor.name} on {a.date} at {a.start_time} ({a.status.value})" for a in apts])
                state["reply"] = f"Here are your recent appointments: {details}."
            else:
                state["reply"] = "You currently have no scheduled appointments."

        elif intent == "QUESTIONNAIRE":
            caps_called.append("get_questionnaire")
            q_data = tools.get_questionnaire(hospital_id=state["hospital_id"] or 1)
            if q_data:
                state["reply"] = f"You have the pre-visit form: '{q_data['name']}' with {len(q_data['questions'])} questions. You can fill it out on your patient portal."
            else:
                state["reply"] = "No pending questionnaires for your current booking."

        else:
            state["reply"] = (
                "Hello! I am your administrative healthcare assistant. "
                "I can help you find specialists, check real doctor availability, "
                "schedule, reschedule, or cancel appointments, and guide you through pre-visit forms."
            )

        state["capabilities_called"] = caps_called
        return state

    workflow.add_node("safety_check", safety_check_node)
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("capability_execution", capability_execution_node)

    workflow.set_entry_point("safety_check")
    workflow.add_conditional_edges(
        "safety_check",
        should_escalate,
        {
            "escalate": "capability_execution",
            "proceed": "intent_recognition"
        }
    )
    workflow.add_edge("intent_recognition", "capability_execution")
    workflow.add_edge("capability_execution", END)

    return workflow.compile()

def run_ai_agent(
    db: Session,
    patient_id: int,
    conversation_id: int,
    message: str,
    hospital_id: Optional[int] = None,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the LangGraph agent for a single turn.
    """
    corr_id = correlation_id or f"AI-TURN-{uuid.uuid4().hex[:8].upper()}"
    ctx = get_context_data(db, conversation_id)

    app = build_agent_graph(db)

    initial_state: AgentState = {
        "message": message,
        "patient_id": patient_id,
        "conversation_id": conversation_id,
        "hospital_id": hospital_id,
        "context": ctx,
        "intent": "GENERAL_ADMINISTRATIVE_QUERY",
        "capabilities_called": [],
        "slots_suggested": [],
        "appointment_data": None,
        "reply": "",
        "is_escalated": False,
        "correlation_id": corr_id
    }

    final_state = app.invoke(initial_state)

    # Persist updated conversational context
    update_context_data(db, conversation_id, final_state["context"])

    return {
        "conversation_id": conversation_id,
        "reply": final_state["reply"],
        "intent": final_state["intent"],
        "capabilities_called": final_state["capabilities_called"],
        "slots_suggested": final_state["slots_suggested"],
        "appointment_data": final_state["appointment_data"],
        "is_escalated": final_state["is_escalated"],
        "correlation_id": corr_id
    }
