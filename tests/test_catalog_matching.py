import unittest

from backend.main import deterministic_catalog_reply, detect_language
from backend.booking_service import BookingState, format_booking_prompt


class CatalogAliasMatchingTests(unittest.TestCase):
    def test_detects_supported_unicode_scripts(self):
        self.assertEqual(detect_language("मुझे कोलेस्ट्रॉल जांच चाहिए"), "Hindi")
        self.assertEqual(detect_language("কোলেস্টেরল পরীক্ষা চাই"), "Bengali")
        self.assertEqual(detect_language("cholesterol test please"), "English")

    def test_exact_hinglish_alias_matches_catalog(self):
        reply = deterministic_catalog_reply("price for khoon ki jaanch")

        self.assertIsNotNone(reply)
        self.assertIn("Complete Blood Count (CBC)", reply)

    def test_exact_devanagari_alias_matches_catalog(self):
        reply = deterministic_catalog_reply("कोलेस्ट्रॉल जांच की कीमत क्या है?")

        self.assertIsNotNone(reply)
        self.assertIn("Lipid Profile (Full)", reply)

    def test_typo_matches_with_rapidfuzz(self):
        reply = deterministic_catalog_reply("what is the cholestrol test price")

        self.assertIsNotNone(reply)
        self.assertIn("Lipid Profile (Full)", reply)

    def test_unknown_test_does_not_match(self):
        self.assertIsNone(deterministic_catalog_reply("price for an allergy panel"))

    def test_catalog_reply_uses_detected_language(self):
        hindi_reply = deterministic_catalog_reply("कोलेस्ट्रॉल जांच की कीमत", "Hindi")
        bengali_reply = deterministic_catalog_reply("cholesterol test price", "Bengali")

        self.assertIn("की कीमत", hindi_reply)
        self.assertIn("এর দাম", bengali_reply)

    def test_booking_prompt_uses_session_language(self):
        state = BookingState(session_id="hindi-demo", detected_language="Hindi", test_name="CBC")

        self.assertIn("पूरा नाम", format_booking_prompt(state))


if __name__ == "__main__":
    unittest.main()
