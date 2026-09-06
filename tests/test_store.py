import tempfile
import unittest
from pathlib import Path

from backend.booking_service import BookingState, format_booking_prompt
from backend.intent_router import classify_intent, is_abusive_message
from backend.store import LabStore


class LabStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = LabStore(str(Path(self.temporary_directory.name) / "labassist.db"))

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_reservation_respects_slot_capacity_and_cancel_reopens_it(self):
        self.store.create_slot("2026-08-01", "08:00", "09:00", capacity=1)
        booking = {
            "patient_name": "Vineet Pandey",
            "phone_number": "9999999999",
            "test_name": "CBC",
            "collection_type": "Home Collection",
            "preferred_date": "2026-08-01",
            "preferred_time": "08:00",
            "collection_address": "12 Example Road",
            "pincode": "110001",
        }

        appointment, error = self.store.reserve_appointment(booking)
        self.assertIsNone(error)
        self.assertEqual(appointment["status"], "confirmed")
        self.assertEqual(self.store.list_available_slots("2026-08-01"), [])

        second_appointment, second_error = self.store.reserve_appointment(booking)
        self.assertIsNone(second_appointment)
        self.assertIn("filled", second_error)

        self.store.cancel_appointment(appointment["id"])
        self.assertEqual(len(self.store.list_available_slots("2026-08-01")), 1)
        self.assertEqual(self.store.dashboard_summary(), {"confirmed": 0, "cancelled": 1, "total": 1})

    def test_booking_state_waits_for_confirmation(self):
        state = BookingState(
            session_id="demo",
            patient_name="Vineet Pandey",
            phone_number="9999999999",
            test_name="CBC",
            preferred_date="2026-08-01",
            preferred_time="08:00",
            collection_address="12 Example Road",
            pincode="110001",
            status="awaiting_confirmation",
        )
        prompt = format_booking_prompt(state)
        self.assertIn("reply with YES", prompt)
        self.assertIn("Do not say the booking is confirmed", prompt)

    def test_greetings_and_abuse_cannot_start_a_booking(self):
        greeting = classify_intent("hi", client=None)
        self.assertEqual(greeting["intent"], "GENERAL_CHAT")
        self.assertTrue(is_abusive_message("fuck"))

    def test_cancel_and_status_lookup_by_id(self):
        self.store.create_slot("2026-08-01", "10:00", "11:00", capacity=1)
        booking = {
            "patient_name": "Vineet Pandey",
            "phone_number": "9999999999",
            "test_name": "LIPID",
            "collection_type": "Home Collection",
            "preferred_date": "2026-08-01",
            "preferred_time": "10:00",
            "collection_address": "12 Example Road",
            "pincode": "110001",
        }
        appointment, error = self.store.reserve_appointment(booking)
        self.assertIsNone(error)
        app_id = appointment["id"]

        with self.store.connection() as conn:
            row = conn.execute("SELECT status FROM appointments WHERE id = ?", (app_id,)).fetchone()
            self.assertEqual(row["status"], "confirmed")

        cancelled = self.store.cancel_appointment(app_id)
        self.assertTrue(cancelled)

        with self.store.connection() as conn:
            row_after = conn.execute("SELECT status FROM appointments WHERE id = ?", (app_id,)).fetchone()
            self.assertEqual(row_after["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
