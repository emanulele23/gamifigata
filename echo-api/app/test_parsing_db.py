import os
import tempfile
import unittest

from app import db
from app.parsing import normalize_log_payload, split_reply_and_data


class ParsingDbTests(unittest.TestCase):
    def test_split_reply_and_data(self):
        reply = (
            "Senti, ha senso.\n"
            '<data>{"pasto": "pasta", "mood_score": 7, "habits_done": ["Corsa"]}</data>'
        )
        spoken, data = split_reply_and_data(reply)
        self.assertEqual(spoken, "Senti, ha senso.")
        self.assertEqual(data["pasto"], "pasta")
        self.assertEqual(data["mood_score"], 7)

    def test_normalize_and_insert(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "echo.db")
            db.init_db(path)
            payload = normalize_log_payload(
                {
                    "pasto": "insalata",
                    "mood_score": 8,
                    "habits_done": ["Meditazione"],
                    "note_salute": "ho dormito poco",
                }
            )
            saved = db.insert_log(path, raw_text="oggi così", source="test", **payload)
            self.assertEqual(saved["pasto"], "insalata")
            self.assertEqual(saved["mood_score"], 8)
            summary = db.context_summary(path)
            self.assertIn("insalata", summary)


if __name__ == "__main__":
    unittest.main()
