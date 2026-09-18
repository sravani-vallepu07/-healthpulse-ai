from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.integrations.telephony import telephony_connector

router = APIRouter(prefix="/telephony", tags=["Telephony & Voice Intake (PRD §11)"])

class InboundCallRequest(BaseModel):
    caller_phone: str
    hospital_id: Optional[int] = None

class CallStreamRequest(BaseModel):
    call_id: str
    speech_transcript: str

class DisconnectCallRequest(BaseModel):
    call_id: str
    reason: str = "NORMAL_CLEARING"

@router.post("/inbound")
def initiate_inbound_call(payload: InboundCallRequest, db: Session = Depends(get_db)):
    """
    PRD §11 Inbound Call Initiation:
    Accepts incoming phone call, recognizes caller by registered phone number,
    and returns initial voice assistant greeting.
    """
    try:
        res = telephony_connector.initiate_inbound_call(
            caller_phone=payload.caller_phone,
            db=db,
            hospital_id=payload.hospital_id
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "TELEPHONY_INIT_FAILED", "message": str(e)})

@router.post("/stream")
def process_audio_stream(payload: CallStreamRequest, db: Session = Depends(get_db)):
    """
    PRD §11 Voice Conversational Stream:
    Streams speech transcription to the identical run_ai_agent pipeline,
    synthesizes speech response, and supports emergency escalation.
    """
    try:
        res = telephony_connector.process_audio_stream(
            call_id=payload.call_id,
            speech_transcript=payload.speech_transcript,
            db=db
        )
        return res
    except KeyError as ke:
        raise HTTPException(status_code=404, detail={"error_code": "CALL_NOT_FOUND", "message": str(ke)})
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"error_code": "CALL_ENDED", "message": str(ve)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "TELEPHONY_STREAM_ERROR", "message": str(e)})

@router.post("/disconnect")
def disconnect_call(payload: DisconnectCallRequest, db: Session = Depends(get_db)):
    """
    PRD §11 Call Disconnect / Failure Handling:
    Gracefully ends call or records carrier/network failures for recovery.
    """
    try:
        res = telephony_connector.handle_call_disconnect(
            call_id=payload.call_id,
            reason=payload.reason,
            db=db
        )
        return res
    except KeyError as ke:
        raise HTTPException(status_code=404, detail={"error_code": "CALL_NOT_FOUND", "message": str(ke)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "TELEPHONY_DISCONNECT_ERROR", "message": str(e)})

@router.get("/calls/{call_id}")
def get_call_details(call_id: str):
    """Retrieves current in-memory call session details and transcript history."""
    session = telephony_connector.get_call_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": f"Call {call_id} not found"})
    return session

@router.post("/webhook/twilio")
async def twilio_voice_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Direct Twilio Voice webhook handler generating valid TwiML XML responses.
    Allows point-and-click integration with real Twilio phone numbers.
    """
    form_data = await request.form()
    caller = form_data.get("From", "+919848022338")
    speech_result = form_data.get("SpeechResult")
    call_sid = form_data.get("CallSid", "TWILIO-CALL-001")

    # If first turn, initiate call
    session = telephony_connector.get_call_session(call_sid)
    if not session:
        init_res = telephony_connector.initiate_inbound_call(caller_phone=caller, db=db)
        # Store under CallSid as well
        telephony_connector._calls[call_sid] = telephony_connector._calls[init_res["call_id"]]
        twiml = telephony_connector.generate_twiml(init_res["greeting"], gather_action_url="/api/telephony/webhook/twilio")
        return Response(content=twiml, media_type="application/xml")

    # If follow-up turn with speech transcription
    if speech_result:
        res = telephony_connector.process_audio_stream(call_id=call_sid, speech_transcript=speech_result, db=db)
        twiml = telephony_connector.generate_twiml(res["agent_reply"], gather_action_url="/api/telephony/webhook/twilio")
        return Response(content=twiml, media_type="application/xml")

    # Default farewell
    telephony_connector.handle_call_disconnect(call_id=call_sid, reason="NORMAL_CLEARING", db=db)
    twiml = telephony_connector.generate_twiml("Thank you for calling HealthPulse AI. Take care and goodbye!")
    return Response(content=twiml, media_type="application/xml")
