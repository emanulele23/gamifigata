import json
import re
from typing import Any, Dict, Optional, Tuple

DATA_RE = re.compile(r"<data>\s*(.*?)\s*</data>", re.DOTALL | re.IGNORECASE)


def split_reply_and_data(reply: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    match = DATA_RE.search(reply or "")
    if not match:
        return (reply or "").strip(), None

    spoken = (reply[: match.start()] + reply[match.end() :]).strip()
    raw = match.group(1).strip()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return spoken, None
        return spoken, payload
    except json.JSONDecodeError:
        return spoken, None


def normalize_log_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if data.get("pasto"):
        out["pasto"] = str(data["pasto"]).strip()
    if data.get("mood_score") is not None and data.get("mood_score") != "":
        try:
            score = int(data["mood_score"])
            if 1 <= score <= 10:
                out["mood_score"] = score
        except (TypeError, ValueError):
            pass
    if data.get("habits_done") is not None:
        out["habits_done"] = data["habits_done"]
    if data.get("note_salute"):
        out["note_salute"] = str(data["note_salute"]).strip()
    if data.get("attivita_fisica") is not None:
        val = data["attivita_fisica"]
        if isinstance(val, bool):
            out["attivita_fisica"] = val
        elif str(val).lower() in ("true", "1", "si", "sì", "yes"):
            out["attivita_fisica"] = True
        elif str(val).lower() in ("false", "0", "no"):
            out["attivita_fisica"] = False
    if data.get("minuti_attivita") is not None and data.get("minuti_attivita") != "":
        try:
            out["minuti_attivita"] = int(data["minuti_attivita"])
        except (TypeError, ValueError):
            pass
    return out
