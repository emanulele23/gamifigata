import os
import tempfile
import unittest

from app import db
from app.onboarding_flow import needs_onboarding, start_onboarding
from app.parsing import normalize_log_payload


class UserFriendlyTests(unittest.TestCase):
    def test_onboarding_not_complete_initially(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "echo.db")
            db.init_db(path)
            self.assertTrue(needs_onboarding(path))
            start_onboarding(path)
            self.assertEqual(db.get_meta(path, "onboarding_step"), "welcome")

    def test_activity_fields(self):
        p = normalize_log_payload({"attivita_fisica": "sì", "minuti_attivita": 15})
        self.assertTrue(p["attivita_fisica"])
        self.assertEqual(p["minuti_attivita"], 15)


if __name__ == "__main__":
    unittest.main()
