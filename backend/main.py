import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from groq import Groq

# Import internal services
from backend.rag_service import get_rag_service
from backend.intent_router import classify_intent
from backend.booking_service import get_or_create_booking_session, format_booking_prompt, active_sessions

# 1. Load Environment Variables
load_dotenv(os.path.expanduser("~/.env"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(
    title="LabAssist AI — Medical Laboratory Conversational API",
    description="Production-grade AI Front Desk for Diagnostic Laboratories with RAG, Intent Routing, and Booking State Machine.",
    version="1.0.0"
)

# Enable CORS for Next.js / React frontend widgets
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request / Response Schemas ---
class ChatRequest(BaseModel):
    session_id: str = Field(default="default-session", description="Unique conversation ID")
    message: str = Field(..., description="User message text")
    language: Optional[str] = Field(default="English", description="Target response language (English, Hindi, Bengali)")

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    confidence: str
    retrieved_context_used: bool

# --- Routes ---
@app.get("/")
def serve_frontend():
    """Serves the main conversational AI front desk web interface."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_dir, "frontend", "index.html")
    return FileResponse(index_path)

@app.get("/api/health")
def health_check():
    """Health check endpoint for Docker / Railway / Render deployments."""
    return {
        "status": "healthy",
        "service": "LabAssist AI",
        "llm_connected": client is not None
    }

@app.get("/api/tests")
def get_all_tests():
    """Returns all diagnostic tests available in the laboratory catalog."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog_path = os.path.join(base_dir, "data", "test_catalog.json")
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@app.post("/api/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest):
    """
    Core Conversational Endpoint:
    1. Classifies user intent (BOOK_APPOINTMENT, CHECK_PRICE_OR_INFO, FAQ_OR_POLICY, etc.)
    2. Retrieves relevant medical catalog or policy context via ChromaDB RAG if applicable
    3. Manages multi-turn appointment booking state if BOOK_APPOINTMENT
    4. Generates empathetic, grounded response in requested language
    """
    if not client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY missing in server configuration.")

    # 1. Classify Intent (or override if session is actively collecting booking fields)
    existing_session = active_sessions.get(req.session_id)
    if existing_session and existing_session.status == "COLLECTING_FIELDS" and existing_session.get_missing_field():
        intent_name = "BOOK_APPOINTMENT"
        confidence = "high (active booking state)"
    else:
        intent_data = classify_intent(req.message, client)
        intent_name = intent_data.get("intent", "GENERAL_CHAT")
        confidence = str(intent_data.get("confidence", "high"))

    rag_service = get_rag_service()
    retrieved_context = ""
    use_rag = False

    # 2. Retrieve RAG Context if asking about tests, prices, fasting, or laboratory policies
    if intent_name in ["CHECK_PRICE_OR_INFO", "FAQ_OR_POLICY"]:
        retrieved_context = rag_service.search_knowledge_base(req.message, n_results=3)
        use_rag = True

    # 3. Handle Booking Workflow
    booking_instructions = ""
    if intent_name == "BOOK_APPOINTMENT":
        booking_state = get_or_create_booking_session(req.session_id)
        lower_msg = req.message.lower()
        for test_keyword in ["cbc", "lipid", "thyroid", "hba1c", "fbs", "lft", "kft", "vitamin d", "vitamin b12", "dengue", "urine", "checkup"]:
            if test_keyword in lower_msg:
                booking_state.test_name = test_keyword.upper()
        
        # If answering a prompt, update missing field
        if not any(w in lower_msg for w in ["want to book", "book a", "schedule a"]):
            booking_state.update_from_message(req.message)

        if not booking_state.get_missing_field() and booking_state.status == "COLLECTING_FIELDS":
            booking_id = booking_state.confirm_booking()
            booking_instructions = f"\nBOOKING CONFIRMED! Appointment ID is {booking_id}. Thank the patient by name ({booking_state.patient_name}) and confirm their slot for {booking_state.preferred_date} at {booking_state.preferred_time}."
        else:
            booking_instructions = "\n" + format_booking_prompt(booking_state)

    # 4. Construct System Prompt
    system_prompt = (
        f"You are LabAssist, a warm, professional, and empathetic AI front desk assistant for a diagnostic medical laboratory in New Delhi.\n"
        f"Your goal is to assist patients with accurate test information, pricing, preparation instructions, and appointment bookings.\n"
        f"IMPORTANT RULES:\n"
        f"- Always answer in {req.language}.\n"
        f"- NEVER invent test prices or fasting hours that are not in the retrieved context.\n"
        f"- If the user asks a medical diagnostic question, remind them to consult a qualified physician after receiving reports.\n"
        f"- Keep responses concise (2-4 sentences max unless detailing a health checkup package).\n"
    )

    if use_rag and retrieved_context:
        system_prompt += f"\n\n{retrieved_context}\n"

    if booking_instructions:
        system_prompt += f"\n\n=== BOOKING STATE INSTRUCTIONS ==={booking_instructions}\n"

    # 5. Generate LLM Reply
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
    except Exception as e:
        reply_text = f"I apologize, our laboratory system is momentarily updating. Please try again or call our helpdesk at +91-8299597072."

    return ChatResponse(
        session_id=req.session_id,
        reply=reply_text,
        intent=intent_name,
        confidence=confidence,
        retrieved_context_used=use_rag
    )

if __name__ == "__main__":
    import uvicorn
    print("Starting LabAssist AI FastAPI server on http://localhost:8000 ...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
