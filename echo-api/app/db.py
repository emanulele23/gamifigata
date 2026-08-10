import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_ora TEXT NOT NULL,
    pasto TEXT,
    mood_score INTEGER,
    habits_done TEXT,
    note_salute TEXT,
    raw_text TEXT,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_logs_data_ora ON health_logs(data_ora);
"""


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _serialize_habits(habits: Any) -> Optional[str]:
    if habits is None:
        return None
    if isinstance(habits, str):
        return habits
    return json.dumps(habits, ensure_ascii=False)


def _deserialize_habits(value: Optional[str]) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def insert_log(
    db_path: str,
    *,
    pasto: Optional[str] = None,
    mood_score: Optional[int] = None,
    habits_done: Any = None,
    note_salute: Optional[str] = None,
    raw_text: Optional[str] = None,
    source: str = "chat",
    data_ora: Optional[str] = None,
) -> Dict[str, Any]:
    ts = data_ora or datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO health_logs
            (data_ora, pasto, mood_score, habits_done, note_salute, raw_text, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                pasto,
                mood_score,
                _serialize_habits(habits_done),
                note_salute,
                raw_text,
                source,
            ),
        )
        row_id = cur.lastrowid
    return get_log(db_path, row_id)


def get_log(db_path: str, row_id: int) -> Dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM health_logs WHERE id = ?", (row_id,)
        ).fetchone()
    if not row:
        raise KeyError(f"log {row_id} not found")
    return _row_to_dict(row)


def recent_logs(db_path: str, limit: int = 10) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM health_logs
            ORDER BY data_ora DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def context_summary(db_path: str, limit: int = 5) -> str:
    logs = recent_logs(db_path, limit=limit)
    if not logs:
        return "Nessun dato recente in archivio."
    lines = []
    for item in reversed(logs):
        bits = [item["data_ora"]]
        if item.get("pasto"):
            bits.append(f"pasto={item['pasto']}")
        if item.get("mood_score") is not None:
            bits.append(f"mood={item['mood_score']}")
        if item.get("habits_done"):
            bits.append(f"habits={item['habits_done']}")
        if item.get("note_salute"):
            bits.append(f"note={item['note_salute']}")
        lines.append(" | ".join(bits))
    return "\n".join(lines)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["habits_done"] = _deserialize_habits(data.get("habits_done"))
    return data
