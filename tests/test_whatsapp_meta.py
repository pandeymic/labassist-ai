import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

from backend.channels.whatsapp_meta import _incoming_text, _valid_signature


class MetaWhatsAppTests(unittest.TestCase):
    def test_signature_requires_meta_app_secret_and_matches_raw_body(self):
        body = b'{"entry":[]}'
        digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()

        with patch.dict(os.environ, {"META_APP_SECRET": "secret"}):
            self.assertTrue(_valid_signature(body, f"sha256={digest}"))
            self.assertFalse(_valid_signature(body + b" ", f"sha256={digest}"))
            self.assertFalse(_valid_signature(body, None))

    def test_interactive_replies_become_booking_messages(self):
        self.assertEqual(
            _incoming_text({
                "type": "interactive",
                "interactive": {"type": "button_reply", "button_reply": {"id": "booking_confirm"}},
            }),
            "YES",
        )
        self.assertEqual(
            _incoming_text({
                "type": "interactive",
                "interactive": {"type": "list_reply", "list_reply": {"id": "slot:2026-10-01:08:00"}},
            }),
            "08:00",
        )

    def test_payload_message_ids_are_stable_json_values(self):
        message = {"id": "wamid.demo", "from": "919999999999", "type": "text", "text": {"body": "hi"}}
        self.assertEqual(json.loads(json.dumps(message))["id"], "wamid.demo")


if __name__ == "__main__":
    unittest.main()
