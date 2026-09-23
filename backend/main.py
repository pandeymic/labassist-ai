import os
import re
import json
from pathlib import Path
from html import escape as escape_html
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from groq import Groq
from rapidfuzz import fuzz, process

# Import internal services
from backend.rag_service import get_rag_service
from backend.intent_router import classify_intent, is_abusive_message
from backend.booking_service import (
    active_sessions,
    confirm_booking,
    format_booking_prompt,
    get_or_create_booking_session,
    is_confirmation,
    save_booking_session,
)
from backend.store import get_store

# 1. Load Environment Variables. Project `.env` is preferred for local runs;
# the home-level file remains a backwards-compatible fallback.
project_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(project_env)
load_dotenv(os.path.expanduser("~/.env"), override=False)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")

client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(
    title="LabAssist AI — Medical Laboratory Conversational API",
    description="Production-grade AI Front Desk for Diagnostic Laboratories with RAG, Intent Routing, and Booking State Machine.",
    version="1.1.0"
)

# Comma-separated production widget origins. Never combine wildcard origins with
# credentialed requests when handling patient data.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request / Response Schemas ---
class ChatRequest(BaseModel):
    session_id: str = Field(default="default-session", description="Unique conversation ID")
    message: str = Field(..., description="User message text")
    language: Optional[str] = Field(default=None, description="Optional language hint; otherwise detected from the message")
    source: str = Field(default="chat", description="Interaction channel: chat, voice, or whatsapp")

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    confidence: str
    retrieved_context_used: bool
    available_slots: List[Dict[str, Any]] = Field(default_factory=list)
    booking_card: Optional[Dict[str, Any]] = None


class SlotCreateRequest(BaseModel):
    appointment_date: str = Field(..., examples=["2026-08-01"])
    start_time: str = Field(..., examples=["08:00"])
    end_time: str = Field(..., examples=["09:00"])
    capacity: int = Field(..., ge=1, le=100)


class LabProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    support_phone: Optional[str] = None
    supported_languages: Optional[List[str]] = None


def require_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    configured_key = os.getenv("LABASSIST_ADMIN_KEY")
    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Administrative API is disabled until LABASSIST_ADMIN_KEY is configured.",
        )
    if x_admin_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid administrative API key.")


def detect_language(message: str) -> str:
    """Detect Hindi, Bengali, or English from the user's Unicode script."""
    if re.search(r"[\u0900-\u097F]", message):
        return "Hindi"
    if re.search(r"[\u0980-\u09FF]", message):
        return "Bengali"
    return "English"


def deterministic_catalog_reply(message: str, language: str = "English") -> Optional[str]:
    """Answer catalog questions with exact and typo-tolerant alias matching."""
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "test_catalog.json"
    records = json.loads(catalog_path.read_text(encoding="utf-8"))

    def normalize(value: str) -> str:
        return " ".join(re.sub(r"[^\w\s]", " ", value.casefold(), flags=re.UNICODE).split())

    normalized = normalize(message)
    candidates = []

    for record in records:
        aliases = [
            record["name"],
            record["test_id"],
            *record.get("aliases", []),
            *record.get("aliases_hi", []),
            *record.get("aliases_hinglish", []),
        ]
        for alias in aliases:
            normalized_alias = normalize(alias)
            if normalized_alias and normalized_alias in normalized:
                return _format_catalog_reply(record, language)
            candidates.append((normalized_alias, record))

    # Compare the complete message against each alias using partial_ratio so
    # natural questions still match, while tolerating small typing errors.
    choices = [alias for alias, _ in candidates if alias]
    fuzzy_match = process.extractOne(normalized, choices, scorer=fuzz.partial_ratio, score_cutoff=86)
    if fuzzy_match:
        _, _, match_index = fuzzy_match
        return _format_catalog_reply(candidates[match_index][1], language)

    return None


def _format_catalog_reply(record: Dict[str, Any], language: str = "English") -> str:
    """Format a deterministic response from one synthetic catalog record."""
    fasting = (
        f"Fasting is required for {record['fasting_hours']} hours."
        if record["fasting_required"]
        else "Fasting is not required."
    )
    english_reply = (
        f"{record['name']} costs ₹{record['price_inr']}. {fasting} "
        f"The expected turnaround is {record['turnaround_time']}. "
        "These details come from the synthetic laboratory catalog."
    )
    if language == "Hindi":
        fasting_hi = (
            f"{record['fasting_hours']} घंटे का उपवास आवश्यक है।"
            if record["fasting_required"]
            else "उपवास आवश्यक नहीं है।"
        )
        return (
            f"{record['name']} की कीमत ₹{record['price_inr']} है। {fasting_hi} "
            f"रिपोर्ट का अनुमानित समय {record['turnaround_time']} है। "
            "ये जानकारी सिंथेटिक लैब कैटलॉग से ली गई है।"
        )
    if language == "Bengali":
        fasting_bn = (
            f"{record['fasting_hours']} ঘণ্টা উপবাস প্রয়োজন।"
            if record["fasting_required"]
            else "উপবাসের প্রয়োজন নেই।"
        )
        return (
            f"{record['name']} এর দাম ₹{record['price_inr']}। {fasting_bn} "
            f"রিপোর্ট পাওয়ার আনুমানিক সময় {record['turnaround_time']}। "
            "এই তথ্য সিন্থেটিক ল্যাব ক্যাটালগ থেকে নেওয়া হয়েছে।"
        )
    return english_reply


def deterministic_reply(
    message: str,
    intent: str,
    booking_instructions: str = "",
    language: str = "English",
) -> str:
    if intent == "CHECK_PRICE_OR_INFO":
        return deterministic_catalog_reply(message, language) or (
            "I can provide approved synthetic catalog details such as price, fasting, "
            "sample type, and turnaround time. Please name the test you want to check."
        )
    if intent == "FAQ_OR_POLICY":
        if language == "Hindi":
            return "मैं सिंथेटिक टेस्ट कैटलॉग और होम-कलेक्शन से जुड़े सवालों में मदद कर सकता हूँ। कृपया किसी खास जांच के बारे में पूछें।"
        if language == "Bengali":
            return "আমি সিন্থেটিক টেস্ট ক্যাটালগ এবং বাড়ি থেকে নমুনা সংগ্রহের প্রশ্নে সাহায্য করতে পারি। নির্দিষ্ট কোনো পরীক্ষা সম্পর্কে জিজ্ঞাসা করুন।"
        return "I can help with synthetic test catalog and home-collection questions. Please ask about a specific test or contact staff for assistance."
    if intent == "BOOK_APPOINTMENT" and booking_instructions:
        return booking_instructions.replace("Ask the patient to", "Please").replace("Ask for", "Please provide")
    if language == "Hindi":
        return "मैं सिंथेटिक टेस्ट की जानकारी, घर से सैंपल संग्रह और अपॉइंटमेंट बुकिंग में मदद कर सकता हूँ।"
    if language == "Bengali":
        return "আমি সিন্থেটিক টেস্টের তথ্য, বাড়ি থেকে নমুনা সংগ্রহ এবং অ্যাপয়েন্টমেন্ট বুকিংয়ে সাহায্য করতে পারি।"
    return "I can help with synthetic test information, home collection, and appointment booking."

# --- Routes ---
@app.get("/")
def serve_frontend():
    """Serves the main conversational AI front desk web interface."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_dir, "frontend", "index.html")
    return FileResponse(index_path)


@app.get("/admin")
def serve_admin_dashboard():
    """A lightweight operations view for the first pilot lab."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return FileResponse(os.path.join(base_dir, "frontend", "admin.html"))

@app.get("/api/health")
def health_check():
    """Health check endpoint for Docker / Railway / Render deployments."""
    return {
        "status": "healthy",
        "service": "LabAssist AI",
        "llm_connected": client is not None
    }


@app.post("/api/live/token")
def create_live_token():
    """Issue a short-lived Gemini Live token without exposing the API key."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured.")
    try:
        from google import genai

        token_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"},
        )
        token = token_client.auth_tokens.create(
            config={
                "uses": 1,
                "live_connect_constraints": {
                    "model": GEMINI_LIVE_MODEL,
                    "config": {
                        "response_modalities": ["AUDIO"],
                        "input_audio_transcription": {},
                        "output_audio_transcription": {},
                        "system_instruction": (
                            "You are Sara, a warm AI front desk assistant for a diagnostic laboratory. "
                            "Answer only operational questions about tests, prices, fasting, timings, "
                            "home collection, and appointments. Never diagnose, interpret reports, "
                            "prescribe, or give treatment advice. If unsure, say a staff member will help. "
                            "For booking, ask the patient to continue in the text chat so LabAssist can "
                            "validate slots and require explicit confirmation."
                        ),
                    },
                },
            }
        )
        token_name = getattr(token, "name", None)
        if not token_name:
            raise RuntimeError("Gemini did not return an ephemeral token")
        return {"token": token_name, "model": GEMINI_LIVE_MODEL}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not create Gemini Live session token.") from exc


def _voice_action_url() -> str:
    """Return the public URL Twilio should call after speech recognition."""
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base_url}/api/webhook/voice/respond"


def _voice_twiml(prompt: str, *, gather: bool = True) -> str:
    """Build a small TwiML response while safely escaping model/user text."""
    escaped_prompt = escape_html(prompt)
    if not gather:
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response><Say language="en-IN">{escaped_prompt}</Say></Response>'''
    action = escape_html(_voice_action_url())
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{action}" method="POST" speechTimeout="auto" language="en-IN">
    <Say language="en-IN">{escaped_prompt}</Say>
  </Gather>
  <Say language="en-IN">I did not hear anything. Please call again if you still need help.</Say>
</Response>'''

@app.get("/api/tests")
def get_all_tests():
    """Returns all diagnostic tests available in the laboratory catalog."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog_path = os.path.join(base_dir, "data", "test_catalog.json")
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


@app.get("/api/lab/profile")
def get_lab_profile():
    """Public, non-sensitive lab identity used by the web widget."""
    profile = get_store().get_profile()
    return {
        "name": profile["name"],
        "city": profile["city"],
        "supported_languages": profile["supported_languages"],
    }


@app.get("/api/slots")
def get_available_slots(appointment_date: str = Query(..., description="Date in YYYY-MM-DD format")):
    return {"appointment_date": appointment_date, "slots": get_store().list_available_slots(appointment_date)}


@app.post("/api/admin/slots", status_code=201)
def create_slot(payload: SlotCreateRequest, _: None = Depends(require_admin_key)):
    """Create an appointment slot for a pilot lab. Requires X-Admin-Key."""
    try:
        return get_store().create_slot(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Slot already exists or could not be created.") from exc


@app.get("/api/admin/appointments")
def get_appointments(status: Optional[str] = None, _: None = Depends(require_admin_key)):
    return {"appointments": get_store().list_appointments(status=status)}


@app.get("/api/admin/dashboard")
def get_dashboard(_: None = Depends(require_admin_key)):
    return {"summary": get_store().dashboard_summary(), "profile": get_store().get_profile()}


@app.post("/api/admin/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str, _: None = Depends(require_admin_key)):
    appointment = get_store().cancel_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return appointment

@app.post("/api/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest):
    """
    Core Conversational Endpoint:
    1. Classifies user intent (BOOK_APPOINTMENT, CHECK_PRICE_OR_INFO, FAQ_OR_POLICY, etc.)
    2. Retrieves relevant medical catalog or policy context via ChromaDB RAG if applicable
    3. Manages multi-turn appointment booking state if BOOK_APPOINTMENT
    4. Generates empathetic, grounded response in requested language
    """
    existing_session = get_or_create_booking_session(req.session_id)
    detected_language = detect_language(req.message)
    # Preserve the session language for numeric/date-only booking turns. A
    # Devanagari or Bengali message always updates the stored language.
    if detected_language != "English" or not existing_session.detected_language:
        existing_session.detected_language = detected_language
        save_booking_session(existing_session)
    response_language = existing_session.detected_language or "English"

    # Never let abusive or unrelated messages become appointment data. Keep the
    # current state intact and give the patient a neutral way back to the task.
    if is_abusive_message(req.message):
        return ChatResponse(
            session_id=req.session_id,
            reply=(
                "मैं टेस्ट की जानकारी, घर से सैंपल संग्रह या अपॉइंटमेंट बुकिंग में मदद कर सकता हूँ। कृपया बताएं कि आपको किस सहायता की जरूरत है।"
                if response_language == "Hindi"
                else "আমি টেস্টের তথ্য, বাড়ি থেকে নমুনা সংগ্রহ বা অ্যাপয়েন্টমেন্ট বুকিংয়ে সাহায্য করতে পারি। কী সাহায্য প্রয়োজন তা বলুন।"
                if response_language == "Bengali"
                else "I’m here to help with test information, home collection, or appointment booking. Please share what you need help with."
            ),
            intent="GENERAL_CHAT",
            confidence="high",
            retrieved_context_used=False,
        )

    # 0. Handle Direct Appointment ID Lookup or Cancellation ("cancel LAB-123456" / "status LAB-123456")
    lab_id_match = re.search(r"\b(LAB-\w{6,})\b", req.message, re.IGNORECASE)
    if lab_id_match:
        target_id = lab_id_match.group(1).upper()
        lower_msg = req.message.lower()
        if any(w in lower_msg for w in ["cancel", "reschedule", "abort", "remove"]):
            cancelled = get_store().cancel_appointment(target_id)
            if cancelled:
                return ChatResponse(
                    session_id=req.session_id,
                    reply=f"Your appointment {target_id} has been cancelled successfully. Let me know if you would like to book a new home collection slot!",
                    intent="CANCEL_OR_RESCHEDULE",
                    confidence="high",
                    retrieved_context_used=False,
                )
            else:
                return ChatResponse(
                    session_id=req.session_id,
                    reply=f"We could not find an active appointment with ID {target_id}. Please verify your Booking ID or call lab helpdesk at +91-8299597072.",
                    intent="CANCEL_OR_RESCHEDULE",
                    confidence="high",
                    retrieved_context_used=False,
                )
        elif any(w in lower_msg for w in ["status", "check", "verify", "details", "when"]):
            with get_store().connection() as conn:
                row = conn.execute("SELECT * FROM appointments WHERE id = ?", (target_id,)).fetchone()
            if row:
                row_dict = dict(row)
                return ChatResponse(
                    session_id=req.session_id,
                    reply=f"Appointment {row_dict['id']}: Status is '{row_dict['status'].upper()}' for {row_dict['patient_name']} ({row_dict['test_name']}) on {row_dict['preferred_date']} at {row_dict['preferred_time']}.",
                    intent="GENERAL_CHAT",
                    confidence="high",
                    retrieved_context_used=False,
                    booking_card=row_dict,
                )

    # 1. Classify Intent (or override if session is actively collecting booking fields)
    has_booking_progress = any(
        [
            existing_session.patient_name,
            existing_session.phone_number,
            existing_session.test_name,
            existing_session.preferred_date,
            existing_session.preferred_time,
            existing_session.collection_address,
            existing_session.pincode,
        ]
    )
    if existing_session.status == "awaiting_confirmation" or (
        existing_session.status == "collecting_fields" and has_booking_progress
    ):
        intent_name = "BOOK_APPOINTMENT"
        confidence = "high (active booking state)"
    else:
        intent_data = classify_intent(req.message, client)
        intent_name = intent_data.get("intent", "GENERAL_CHAT")
        confidence = str(intent_data.get("confidence", "high"))

        # The local fallback classifier is intentionally small. A known test
        # alias plus a non-booking message is enough to identify a catalog
        # question even when the message is written entirely in Hindi/Bengali.
        catalog_reply = deterministic_catalog_reply(req.message, response_language)
        booking_words = (
            "book", "schedule", "appointment", "बुक", "अपॉइंटमेंट", "बुकिंग",
            "অ্যাপয়েন্টমেন্ট", "বুকিং", "বুক",
        )
        if intent_name == "GENERAL_CHAT" and catalog_reply and not any(
            word in req.message.casefold() for word in booking_words
        ):
            intent_name = "CHECK_PRICE_OR_INFO"
            confidence = "high (catalog alias match)"

    # Resolve known catalog aliases before initializing or querying the vector
    # index. This keeps common Hindi/Hinglish requests deterministic and fast.
    if intent_name == "CHECK_PRICE_OR_INFO":
        catalog_reply = catalog_reply or deterministic_catalog_reply(req.message, response_language)
        if catalog_reply:
            return ChatResponse(
                session_id=req.session_id,
                reply=catalog_reply,
                intent=intent_name,
                confidence="high (catalog alias match)",
                retrieved_context_used=False,
            )

    rag_service = get_rag_service()
    retrieved_context = ""
    use_rag = False

    # 2. Retrieve RAG Context if asking about tests, prices, fasting, or laboratory policies
    if client and intent_name in ["CHECK_PRICE_OR_INFO", "FAQ_OR_POLICY"]:
        retrieved_context = rag_service.search_knowledge_base(req.message, n_results=3)
        use_rag = True

    # 3. Handle Booking Workflow
    booking_instructions = ""
    confirmed_card = None
    if intent_name == "BOOK_APPOINTMENT":
        booking_state = existing_session
        booking_state.detected_language = response_language
        lower_msg = req.message.lower()
        for test_keyword in ["cbc", "lipid", "thyroid", "hba1c", "fbs", "lft", "kft", "vitamin d", "vitamin b12", "dengue", "urine", "checkup"]:
            if test_keyword in lower_msg:
                booking_state.test_name = test_keyword.upper()

        if booking_state.status == "awaiting_confirmation" and is_confirmation(req.message):
            appointment, booking_error = confirm_booking(booking_state)
            if appointment:
                appointment["source"] = req.source
                with get_store().connection() as connection:
                    connection.execute(
                        "UPDATE appointments SET source = ?, updated_at = updated_at WHERE id = ?",
                        (req.source, appointment["id"]),
                    )
                confirmed_card = appointment
                booking_instructions = (
                    f"The booking is confirmed. Appointment ID: {appointment['id']}. "
                    f"Confirm {appointment['preferred_date']} at {appointment['preferred_time']} and say a staff member will contact them if anything changes."
                )
            else:
                booking_state.status = "collecting_fields"
                save_booking_session(booking_state)
                booking_instructions = f"The booking could not be confirmed: {booking_error} Ask the patient for another time."
        elif booking_state.status == "awaiting_confirmation":
            booking_instructions = format_booking_prompt(booking_state)
        else:
            # The state machine collects one missing value at a time. A message
            # that begins a booking should not be incorrectly stored as a name.
            validation_error = None
            available_slots: List[Dict[str, Any]] = []
            if not any(w in lower_msg for w in ["want to book", "book a", "schedule a", "need a test"]):
                _, validation_error = booking_state.update_from_message(req.message)

            if validation_error:
                save_booking_session(booking_state)
                return ChatResponse(
                    session_id=req.session_id,
                    reply=f"{validation_error} {format_booking_prompt(booking_state)}",
                    intent="BOOK_APPOINTMENT",
                    confidence="high (active booking state)",
                    retrieved_context_used=False,
                )

            # Immediately after a valid date, expose only real slots. The
            # browser turns these into buttons, while the server still verifies
            # capacity when the patient confirms.
            if booking_state.get_missing_field() == "preferred_time" and booking_state.preferred_date:
                requested_date = booking_state.preferred_date
                available_slots = get_store().list_available_slots(booking_state.preferred_date)
                if not available_slots:
                    booking_state.preferred_date = None
                    save_booking_session(booking_state)
                    return ChatResponse(
                        session_id=req.session_id,
                        reply=(
                            f"There are no available home-collection slots on {requested_date}. "
                            "Please provide another date in YYYY-MM-DD format."
                        ),
                        intent="BOOK_APPOINTMENT",
                        confidence="high (active booking state)",
                        retrieved_context_used=False,
                    )

            # Reject a syntactically valid time if staff have not opened it.
            if booking_state.preferred_date and booking_state.preferred_time:
                valid_times = {slot["start_time"] for slot in get_store().list_available_slots(booking_state.preferred_date)}
                if booking_state.preferred_time not in valid_times:
                    booking_state.preferred_time = None
                    save_booking_session(booking_state)
                    available_slots = get_store().list_available_slots(booking_state.preferred_date)
                    return ChatResponse(
                        session_id=req.session_id,
                        reply="That time is not available. Please choose one of the available slots below.",
                        intent="BOOK_APPOINTMENT",
                        confidence="high (active booking state)",
                        retrieved_context_used=False,
                        available_slots=available_slots,
                    )

            if not booking_state.get_missing_field():
                booking_state.status = "awaiting_confirmation"
            save_booking_session(booking_state)
            booking_instructions = format_booking_prompt(booking_state)

    # 4. Construct System Prompt
    system_prompt = (
        f"You are LabAssist, a warm, professional, and empathetic AI front desk assistant for a diagnostic medical laboratory.\n"
        f"Your goal is to assist patients with accurate test information, pricing, preparation instructions, and appointment bookings.\n"
        f"IMPORTANT RULES:\n"
        f"- Always answer in {response_language}.\n"
        f"- NEVER invent test prices or fasting hours that are not in the retrieved context.\n"
        f"- If the user asks a medical diagnostic question, remind them to consult a qualified physician after receiving reports.\n"
        f"- Never interpret results, diagnose, prescribe, or give treatment advice. Escalate those requests to staff.\n"
        f"- A booking is confirmed only when the booking instructions explicitly say it is confirmed.\n"
        f"- Keep responses concise (2-4 sentences max unless detailing a health checkup package).\n"
    )

    if use_rag and retrieved_context:
        system_prompt += f"\n\n{retrieved_context}\n"

    if booking_instructions:
        system_prompt += f"\n\n=== BOOKING STATE INSTRUCTIONS ==={booking_instructions}\n"

    # 5. Generate LLM Reply
    if not client:
        reply_text = deterministic_reply(req.message, intent_name, booking_instructions, response_language)
    else:
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.message}
                ],
                temperature=0.3
            )
            reply_text = completion.choices[0].message.content
        except Exception:
            reply_text = deterministic_reply(req.message, intent_name, booking_instructions, response_language)

    return ChatResponse(
        session_id=req.session_id,
        reply=reply_text,
        intent=intent_name,
        confidence=confidence,
        retrieved_context_used=use_rag,
        available_slots=available_slots if intent_name == "BOOK_APPOINTMENT" and "available_slots" in locals() else [],
        booking_card=confirmed_card,
    )


@app.post("/api/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Twilio / WhatsApp Business Webhook for LabAssist AI after-hours pilot.
    Receives incoming WhatsApp messages, routes through the conversational FSM,
    and returns TwiML / XML reply to respond automatically on WhatsApp.
    """
    form_data = await request.form()
    sender = form_data.get("From", "whatsapp:unknown")
    body = form_data.get("Body", "").strip()

    # Route through existing core chat handler
    chat_req = ChatRequest(
        session_id=sender,
        message=body,
        source="whatsapp",
    )
    chat_res = handle_chat(chat_req)

    # Format TwiML XML response for WhatsApp
    reply_text = chat_res.reply
    if chat_res.booking_card:
        reply_text += (
            f"\n\n🏥 *CONFIRMED HOME COLLECTION*\n"
            f"ID: {chat_res.booking_card['id']}\n"
            f"Patient: {chat_res.booking_card['patient_name']} ({chat_res.booking_card['phone_number']})\n"
            f"Test: {chat_res.booking_card['test_name']}\n"
            f"Date/Time: {chat_res.booking_card['preferred_date']} at {chat_res.booking_card['preferred_time']}\n"
            f"Address: {chat_res.booking_card['collection_address']}"
        )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escape_html(reply_text)}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/api/webhook/voice")
async def voice_webhook(request: Request):
    """Start a phone conversation from a Twilio voice webhook."""
    form_data = await request.form()
    call_sid = str(form_data.get("CallSid", "unknown-call"))
    profile = get_store().get_profile()
    greeting = (
        f"Hello, you have reached {profile['name']}. "
        "I can help with test information, prices, home collection, or booking an appointment. "
        "How may I help you?"
    )
    return Response(content=_voice_twiml(greeting), media_type="application/xml")


@app.post("/api/webhook/voice/respond")
async def voice_respond(request: Request):
    """Receive Twilio's speech transcript and continue the shared chat workflow."""
    form_data = await request.form()
    call_sid = str(form_data.get("CallSid", "unknown-call"))
    speech = str(form_data.get("SpeechResult", "")).strip()
    if not speech:
        return Response(
            content=_voice_twiml("Sorry, I did not catch that. Please tell me what you need help with."),
            media_type="application/xml",
        )

    chat_res = handle_chat(
        ChatRequest(session_id=f"voice:{call_sid}", message=speech, source="voice")
    )
    reply = chat_res.reply
    if chat_res.booking_card:
        card = chat_res.booking_card
        reply += (
            f" Your booking ID is {card['id']}. "
            f"The collection is scheduled for {card['preferred_date']} at {card['preferred_time']}."
        )
    return Response(content=_voice_twiml(reply), media_type="application/xml")


if __name__ == "__main__":
    import uvicorn
    print("Starting LabAssist AI FastAPI server on http://localhost:8000 ...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
