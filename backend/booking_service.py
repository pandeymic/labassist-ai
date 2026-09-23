"""Persistent, confirmation-first appointment workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any, Optional

from backend.store import get_store


@dataclass
class BookingState:
    session_id: str
    detected_language: Optional[str] = None
    status: str = "collecting_fields"
    patient_name: Optional[str] = None
    phone_number: Optional[str] = None
    test_name: Optional[str] = None
    collection_type: str = "Home Collection"
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    collection_address: Optional[str] = None
    pincode: Optional[str] = None
    booking_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BookingState":
        fields = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        return cls(**fields)

    def get_missing_field(self) -> Optional[str]:
        required = ["test_name", "patient_name", "phone_number", "preferred_date", "preferred_time"]
        if self.collection_type == "Home Collection":
            required.extend(["collection_address", "pincode"])
        for field in required:
            if not getattr(self, field):
                return field
        return None

    def update_from_message(self, message: str) -> tuple[bool, Optional[str]]:
        missing = self.get_missing_field()
        value = message.strip()
        if not missing or not value:
            return False, "Please provide the requested booking detail."

        error = self._validate_field(missing, value)
        if error:
            return False, error
        setattr(self, missing, value)
        return True, None

    @staticmethod
    def _validate_field(field: str, value: str) -> Optional[str]:
        lowered = value.lower()
        banned = {"fuck", "fucking", "shit", "bitch", "asshole", "madarchod", "bhenchod"}
        if any(term in lowered for term in banned):
            return "I can help when you are ready to share the requested booking detail."
        if field == "patient_name" and (len(value) < 2 or not re.search(r"[A-Za-z]", value)):
            return "Please enter the patient's full name using letters."
        if field == "phone_number" and not re.fullmatch(r"(?:\+91[- ]?)?[6-9]\d{9}", value.replace(" ", "")):
            return "Please enter a valid 10-digit Indian mobile number."
        if field == "preferred_date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return "Please enter the collection date in YYYY-MM-DD format."
        if field == "preferred_time" and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            return "Please enter a time in 24-hour HH:MM format, for example 08:00."
        if field == "pincode" and not re.fullmatch(r"\d{6}", value):
            return "Please enter a valid 6-digit pincode."
        if field == "collection_address" and len(value) < 8:
            return "Please enter a complete home-collection address."
        return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def booking_payload(self) -> dict[str, Any]:
        return {
            "patient_name": self.patient_name,
            "phone_number": self.phone_number,
            "test_name": self.test_name,
            "collection_type": self.collection_type,
            "preferred_date": self.preferred_date,
            "preferred_time": self.preferred_time,
            "collection_address": self.collection_address,
            "pincode": self.pincode,
        }


active_sessions: dict[str, BookingState] = {}


def get_or_create_booking_session(session_id: str) -> BookingState:
    if session_id not in active_sessions:
        saved = get_store().load_session(session_id)
        active_sessions[session_id] = BookingState.from_dict(saved) if saved else BookingState(session_id=session_id)
    return active_sessions[session_id]


def save_booking_session(state: BookingState) -> None:
    active_sessions[state.session_id] = state
    get_store().save_session(state.session_id, state.to_dict())


def is_confirmation(message: str) -> bool:
    return message.strip().lower() in {"yes", "yes please", "confirm", "confirmed", "i confirm", "haan", "ha", "हाँ"}


def confirm_booking(state: BookingState) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    appointment, error = get_store().reserve_appointment(state.booking_payload())
    if appointment:
        state.status = "confirmed"
        state.booking_id = appointment["id"]
        save_booking_session(state)
    return appointment, error


def format_booking_prompt(state: BookingState) -> str:
    language = state.detected_language or "English"
    if state.status == "awaiting_confirmation":
        if language == "Hindi":
            return (
                "कृपया इन विवरणों की पुष्टि होने पर केवल YES लिखें:\n"
                f"- मरीज का नाम: {state.patient_name}\n"
                f"- फोन: {state.phone_number}\n"
                f"- जांच: {state.test_name}\n"
                f"- सैंपल संग्रह: {state.collection_type}\n"
                f"- तारीख और समय: {state.preferred_date} को {state.preferred_time}\n"
                f"- पता: {state.collection_address or 'लैब विजिट'}\n"
                f"- पिनकोड: {state.pincode or 'उपलब्ध नहीं'}\n"
                "अभी बुकिंग की पुष्टि नहीं हुई है।"
            )
        if language == "Bengali":
            return (
                "এই তথ্যগুলি সঠিক হলে শুধুমাত্র YES লিখে নিশ্চিত করুন:\n"
                f"- রোগীর নাম: {state.patient_name}\n"
                f"- ফোন: {state.phone_number}\n"
                f"- পরীক্ষা: {state.test_name}\n"
                f"- নমুনা সংগ্রহ: {state.collection_type}\n"
                f"- তারিখ ও সময়: {state.preferred_date}, {state.preferred_time}\n"
                f"- ঠিকানা: {state.collection_address or 'ল্যাব ভিজিট'}\n"
                f"- পিনকোড: {state.pincode or 'নেই'}\n"
                "এখনও বুকিং নিশ্চিত হয়নি।"
            )
        return (
            "Ask the patient to reply with YES only if these details are correct:\n"
            f"- Patient Name: {state.patient_name}\n"
            f"- Phone: {state.phone_number}\n"
            f"- Test: {state.test_name}\n"
            f"- Collection: {state.collection_type}\n"
            f"- Date and time: {state.preferred_date} at {state.preferred_time}\n"
            f"- Address: {state.collection_address or 'Lab visit'}\n"
            f"- Pincode: {state.pincode or 'N/A'}\n"
            "Do not say the booking is confirmed yet."
        )

    prompts = {
        "test_name": "Ask which laboratory test or health package the patient wants to book.",
        "patient_name": "Ask for the patient's full name for the booking.",
        "phone_number": "Ask for a 10-digit mobile number for booking updates.",
        "preferred_date": "Ask for the preferred collection date in YYYY-MM-DD format.",
        "preferred_time": "Ask for a preferred time matching an available slot, such as 08:00.",
        "collection_address": "Ask for the complete home-collection address.",
        "pincode": "Ask for the home-collection pincode.",
    }
    english_prompt = prompts.get(state.get_missing_field(), "How can I assist with the appointment?")
    if language == "Hindi":
        return {
            "test_name": "कृपया बताएं कि आप कौन-सी लैब जांच या हेल्थ पैकेज बुक करना चाहते हैं।",
            "patient_name": "कृपया मरीज का पूरा नाम बताएं।",
            "phone_number": "कृपया बुकिंग अपडेट के लिए 10 अंकों का मोबाइल नंबर बताएं।",
            "preferred_date": "कृपया पसंदीदा सैंपल संग्रह तारीख YYYY-MM-DD प्रारूप में बताएं।",
            "preferred_time": "कृपया उपलब्ध स्लॉट में से समय चुनें, जैसे 08:00।",
            "collection_address": "कृपया घर से सैंपल संग्रह का पूरा पता बताएं।",
            "pincode": "कृपया घर से सैंपल संग्रह का पिनकोड बताएं।",
        }.get(state.get_missing_field(), "मैं आपकी कैसे सहायता कर सकता हूँ?")
    if language == "Bengali":
        return {
            "test_name": "আপনি কোন ল্যাব পরীক্ষা বা স্বাস্থ্য প্যাকেজ বুক করতে চান তা বলুন।",
            "patient_name": "রোগীর পুরো নাম বলুন।",
            "phone_number": "বুকিং আপডেটের জন্য ১০ সংখ্যার মোবাইল নম্বর বলুন।",
            "preferred_date": "পছন্দের নমুনা সংগ্রহের তারিখ YYYY-MM-DD ফরম্যাটে বলুন।",
            "preferred_time": "উপলব্ধ স্লট থেকে একটি সময় বেছে নিন, যেমন 08:00।",
            "collection_address": "বাড়ি থেকে নমুনা সংগ্রহের সম্পূর্ণ ঠিকানা বলুন।",
            "pincode": "বাড়ি থেকে নমুনা সংগ্রহের পিনকোড বলুন।",
        }.get(state.get_missing_field(), "আমি কীভাবে সাহায্য করতে পারি?")
    return english_prompt
