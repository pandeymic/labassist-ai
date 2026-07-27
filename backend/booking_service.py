from typing import Dict, Any, Optional
import uuid

class BookingState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status = "COLLECTING_FIELDS" # COLLECTING_FIELDS -> CONFIRMED -> CANCELLED
        self.patient_name: Optional[str] = None
        self.phone_number: Optional[str] = None
        self.test_name: Optional[str] = None
        self.collection_type: str = "Home Collection" # 'Home Collection' or 'Lab Visit'
        self.preferred_date: Optional[str] = None
        self.preferred_time: Optional[str] = None
        self.booking_id: Optional[str] = None

    def get_missing_field(self) -> Optional[str]:
        if not self.test_name:
            return "test_name"
        if not self.patient_name:
            return "patient_name"
        if not self.phone_number:
            return "phone_number"
        if not self.preferred_date:
            return "preferred_date"
        if not self.preferred_time:
            return "preferred_time"
        return None

    def update_from_message(self, message: str):
        missing = self.get_missing_field()
        clean_msg = message.strip()
        if not clean_msg:
            return
        if missing == "test_name":
            self.test_name = clean_msg
        elif missing == "patient_name":
            self.patient_name = clean_msg
        elif missing == "phone_number":
            self.phone_number = clean_msg
        elif missing == "preferred_date":
            self.preferred_date = clean_msg
        elif missing == "preferred_time":
            self.preferred_time = clean_msg

    def confirm_booking(self) -> str:
        self.status = "CONFIRMED"
        self.booking_id = f"LAB-{uuid.uuid4().hex[:6].upper()}"
        return self.booking_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "booking_id": self.booking_id,
            "patient_name": self.patient_name,
            "phone_number": self.phone_number,
            "test_name": self.test_name,
            "collection_type": self.collection_type,
            "preferred_date": self.preferred_date,
            "preferred_time": self.preferred_time
        }

# Simple in-memory session store for appointments
active_sessions: Dict[str, BookingState] = {}

def get_or_create_booking_session(session_id: str) -> BookingState:
    if session_id not in active_sessions:
        active_sessions[session_id] = BookingState(session_id)
    return active_sessions[session_id]

def format_booking_prompt(state: BookingState) -> str:
    missing = state.get_missing_field()
    if not missing:
        return (
            f"All booking details collected! Ask the patient to confirm their appointment:\n"
            f"- Patient Name: {state.patient_name}\n"
            f"- Phone: {state.phone_number}\n"
            f"- Test: {state.test_name}\n"
            f"- Date & Time: {state.preferred_date} at {state.preferred_time}\n"
            f"- Type: {state.collection_type}"
        )
    
    prompts = {
        "test_name": "Ask the patient which laboratory test or health package they would like to book.",
        "patient_name": "Ask the patient for their full name for the booking.",
        "phone_number": "Ask the patient for their 10-digit mobile number so we can send SMS/WhatsApp reports.",
        "preferred_date": "Ask the patient for their preferred date for sample collection (e.g., Tomorrow morning).",
        "preferred_time": "Ask the patient for their preferred time slot between 6:00 AM and 8:00 PM."
    }
    return prompts.get(missing, "How can I assist with your appointment?")
