import unittest

from backend.main import deterministic_catalog_reply


class CatalogAliasMatchingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
