import os
import tempfile
import unittest

from app import db
from app.goals_engine import update_streaks_from_log
from app.parsing import normalize_log_payload, split_reply_and_data


class ParsingDbTests(unittest.TestCase):
    def test_split_reply_and_data(self):
        reply = (
            "Senti, ha senso.\n"
            '<data>{"pasto": "pasta", "mood_score": 7, "habits_done": ["Corsa"], '
            '"attivita_fisica": true, "minuti_attivita": 30}</data>'
        )
        spoken, data = split_reply_and_data(reply)
        self.assertEqual(spoken, "Senti, ha senso.")
        self.assertEqual(data["pasto"], "pasta")
        self.assertTrue(data["attivita_fisica"])

    def test_normalize_activity(self):
        payload = normalize_log_payload(
            {"attivita_fisica": "si", "minuti_attivita": 25}
        )
        self.assertTrue(payload["attivita_fisica"])
        self.assertEqual(payload["minuti_attivita"], 25)

    def test_profile_goals_streaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "echo.db")
            db.init_db(path)
            db.save_profile(
                path,
                name="Marco",
                checkin_times=["09:00", "21:00"],
                onboarding_complete=True,
            )
            goal = db.add_goal(path, title="Corsa", category="fitness")
            db.insert_log(
                path,
                habits_done=["Corsa"],
                attivita_fisica=True,
                source="test",
            )
            update_streaks_from_log(path, {"habits_done": ["Corsa"]})
            streaks = db.get_streaks(path)
            self.assertEqual(streaks[0]["current_streak"], 1)

    def test_apple_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "echo.db")
            db.init_db(path)
            saved = db.upsert_apple_health(path, day="2026-08-10", steps=9000)
            self.assertEqual(saved["steps"], 9000)
            summary = db.apple_health_summary(path, day="2026-08-10")
            self.assertIn("9000", summary)


if __name__ == "__main__":
    unittest.main()
