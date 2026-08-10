"""Database schema and CRUD for Echo."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
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
    attivita_fisica INTEGER,
    minuti_attivita INTEGER,
    checkin_slot TEXT,
    raw_text TEXT,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_logs_data_ora ON health_logs(data_ora);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_ora TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    chat_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_data_ora ON messages(data_ora);

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT,
    timezone TEXT DEFAULT 'Europe/Rome',
    checkin_times TEXT,
    onboarding_complete INTEGER DEFAULT 0,
    prefer_calls INTEGER DEFAULT 1,
    apple_health_enabled INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    metric TEXT DEFAULT 'daily',
    target_value REAL,
    unit TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS streaks (
    goal_id INTEGER PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    last_done_date TEXT,
    FOREIGN KEY(goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS apple_health_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL UNIQUE,
    steps INTEGER,
    active_energy_kcal REAL,
    exercise_minutes REAL,
    sleep_hours REAL,
    workouts_json TEXT,
    synced_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_apple_health_day ON apple_health_daily(day);
"""

MIGRATIONS = [
    "ALTER TABLE health_logs ADD COLUMN attivita_fisica INTEGER",
    "ALTER TABLE health_logs ADD COLUMN minuti_attivita INTEGER",
    "ALTER TABLE health_logs ADD COLUMN checkin_slot TEXT",
]

_initialized: set[str] = set()


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        for stmt in MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        conn.commit()
    _initialized.add(db_path)


def ensure_db(db_path: str) -> None:
    if db_path not in _initialized:
        init_db(db_path)


@contextmanager
def connect(db_path: str):
    ensure_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _serialize_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _deserialize_json(value: Optional[str]) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _serialize_habits(habits: Any) -> Optional[str]:
    return _serialize_json(habits)


def _deserialize_habits(value: Optional[str]) -> Any:
    return _deserialize_json(value)


def get_meta(db_path: str, key: str) -> Optional[str]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None


def set_meta(db_path: str, key: str, value: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO meta(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def resolve_chat_id(db_path: str, configured: str = "") -> Optional[str]:
    if configured:
        return str(configured)
    return get_meta(db_path, "telegram_chat_id")


def remember_chat_id(db_path: str, chat_id: str) -> None:
    set_meta(db_path, "telegram_chat_id", str(chat_id))


# --- Profile ---


def get_profile(db_path: str) -> Dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    if not row:
        return {
            "name": None,
            "timezone": "Europe/Rome",
            "checkin_times": ["09:00", "14:00", "21:00"],
            "onboarding_complete": False,
            "prefer_calls": True,
            "apple_health_enabled": False,
        }
    data = dict(row)
    data["checkin_times"] = _deserialize_json(data.get("checkin_times")) or [
        "09:00",
        "14:00",
        "21:00",
    ]
    data["onboarding_complete"] = bool(data.get("onboarding_complete"))
    data["prefer_calls"] = bool(data.get("prefer_calls", 1))
    data["apple_health_enabled"] = bool(data.get("apple_health_enabled", 0))
    return data


def save_profile(db_path: str, **fields: Any) -> Dict[str, Any]:
    current = get_profile(db_path)
    current.update({k: v for k, v in fields.items() if v is not None})
    times = current.get("checkin_times") or ["09:00", "14:00", "21:00"]
    ts = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_profile
            (id, name, timezone, checkin_times, onboarding_complete,
             prefer_calls, apple_health_enabled, created_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                timezone = excluded.timezone,
                checkin_times = excluded.checkin_times,
                onboarding_complete = excluded.onboarding_complete,
                prefer_calls = excluded.prefer_calls,
                apple_health_enabled = excluded.apple_health_enabled
            """,
            (
                current.get("name"),
                current.get("timezone", "Europe/Rome"),
                _serialize_json(times),
                1 if current.get("onboarding_complete") else 0,
                1 if current.get("prefer_calls", True) else 0,
                1 if current.get("apple_health_enabled") else 0,
                ts,
            ),
        )
    return get_profile(db_path)


def is_onboarding_complete(db_path: str) -> bool:
    return bool(get_profile(db_path).get("onboarding_complete"))


# --- Goals & streaks ---


def list_goals(db_path: str, *, active_only: bool = True) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM goals WHERE active = 1 ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM goals ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def add_goal(
    db_path: str,
    *,
    title: str,
    description: str = "",
    category: str = "crescita",
    metric: str = "daily",
    target_value: Optional[float] = None,
    unit: str = "",
) -> Dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO goals
            (title, description, category, metric, target_value, unit, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (title, description, category, metric, target_value, unit, ts),
        )
        goal_id = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO streaks (goal_id, current_streak, best_streak) VALUES (?, 0, 0)",
            (goal_id,),
        )
    goals = list_goals(db_path, active_only=False)
    return next(g for g in goals if g["id"] == goal_id)


def get_streaks(db_path: str) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT g.id AS goal_id, g.title, g.category, g.unit,
                   s.current_streak, s.best_streak, s.last_done_date
            FROM goals g
            LEFT JOIN streaks s ON s.goal_id = g.id
            WHERE g.active = 1
            ORDER BY g.id
            """
        ).fetchall()
    return [dict(r) for r in rows]


def record_goal_progress(
    db_path: str,
    goal_id: int,
    *,
    done: bool,
    day: Optional[str] = None,
) -> Dict[str, Any]:
    today = day or date.today().isoformat()
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM streaks WHERE goal_id = ?", (goal_id,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO streaks (goal_id, current_streak, best_streak) VALUES (?, 0, 0)",
                (goal_id,),
            )
            row = conn.execute(
                "SELECT * FROM streaks WHERE goal_id = ?", (goal_id,)
            ).fetchone()

        current = row["current_streak"] or 0
        best = row["best_streak"] or 0
        last = row["last_done_date"]

        if done:
            if last == today:
                new_current = current
            elif last and _is_yesterday(last, today):
                new_current = current + 1
            else:
                new_current = 1
            new_best = max(best, new_current)
            conn.execute(
                """
                UPDATE streaks
                SET current_streak = ?, best_streak = ?, last_done_date = ?
                WHERE goal_id = ?
                """,
                (new_current, new_best, today, goal_id),
            )
        updated = conn.execute(
            "SELECT * FROM streaks WHERE goal_id = ?", (goal_id,)
        ).fetchone()
    return dict(updated)


def _is_yesterday(last: str, today: str) -> bool:
    try:
        d_last = date.fromisoformat(last[:10])
        d_today = date.fromisoformat(today[:10])
        return (d_today - d_last).days == 1
    except ValueError:
        return False


def goals_summary(db_path: str) -> str:
    streaks = get_streaks(db_path)
    if not streaks:
        return "Nessun obiettivo attivo."
    lines = []
    for s in streaks:
        lines.append(
            f"- {s['title']}: streak {s.get('current_streak') or 0} "
            f"(record {s.get('best_streak') or 0})"
        )
    return "\n".join(lines)


# --- Apple Health ---


def upsert_apple_health(
    db_path: str,
    *,
    day: str,
    steps: Optional[int] = None,
    active_energy_kcal: Optional[float] = None,
    exercise_minutes: Optional[float] = None,
    sleep_hours: Optional[float] = None,
    workouts: Optional[Any] = None,
) -> Dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO apple_health_daily
            (day, steps, active_energy_kcal, exercise_minutes, sleep_hours, workouts_json, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
                steps = COALESCE(excluded.steps, apple_health_daily.steps),
                active_energy_kcal = COALESCE(excluded.active_energy_kcal, apple_health_daily.active_energy_kcal),
                exercise_minutes = COALESCE(excluded.exercise_minutes, apple_health_daily.exercise_minutes),
                sleep_hours = COALESCE(excluded.sleep_hours, apple_health_daily.sleep_hours),
                workouts_json = COALESCE(excluded.workouts_json, apple_health_daily.workouts_json),
                synced_at = excluded.synced_at
            """,
            (
                day[:10],
                steps,
                active_energy_kcal,
                exercise_minutes,
                sleep_hours,
                _serialize_json(workouts),
                ts,
            ),
        )
        row = conn.execute(
            "SELECT * FROM apple_health_daily WHERE day = ?", (day[:10],)
        ).fetchone()
    data = dict(row)
    data["workouts"] = _deserialize_json(data.pop("workouts_json", None))
    return data


def get_apple_health(db_path: str, day: Optional[str] = None) -> Optional[Dict[str, Any]]:
    target = (day or date.today().isoformat())[:10]
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM apple_health_daily WHERE day = ?", (target,)
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["workouts"] = _deserialize_json(data.pop("workouts_json", None))
    return data


def apple_health_summary(db_path: str, day: Optional[str] = None) -> str:
    data = get_apple_health(db_path, day)
    if not data:
        return "Nessun dato Apple Salute per oggi."
    bits = [f"giorno={data['day']}"]
    if data.get("steps") is not None:
        bits.append(f"passi={data['steps']}")
    if data.get("exercise_minutes") is not None:
        bits.append(f"minuti_esercizio={data['exercise_minutes']}")
    if data.get("active_energy_kcal") is not None:
        bits.append(f"kcal_attive={data['active_energy_kcal']}")
    if data.get("sleep_hours") is not None:
        bits.append(f"sonno_ore={data['sleep_hours']}")
    if data.get("workouts"):
        bits.append(f"workout={data['workouts']}")
    return " | ".join(bits)


# --- Messages & logs ---


def add_message(
    db_path: str,
    role: str,
    content: str,
    *,
    chat_id: Optional[str] = None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages (data_ora, role, content, chat_id)
            VALUES (?, ?, ?, ?)
            """,
            (ts, role, content, chat_id),
        )


def recent_messages(
    db_path: str,
    limit: int = 8,
    *,
    chat_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    with connect(db_path) as conn:
        if chat_id:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE chat_id = ? OR chat_id IS NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (str(chat_id), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]


def insert_log(
    db_path: str,
    *,
    pasto: Optional[str] = None,
    mood_score: Optional[int] = None,
    habits_done: Any = None,
    note_salute: Optional[str] = None,
    attivita_fisica: Optional[bool] = None,
    minuti_attivita: Optional[int] = None,
    checkin_slot: Optional[str] = None,
    raw_text: Optional[str] = None,
    source: str = "chat",
    data_ora: Optional[str] = None,
) -> Dict[str, Any]:
    ts = data_ora or datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO health_logs
            (data_ora, pasto, mood_score, habits_done, note_salute,
             attivita_fisica, minuti_attivita, checkin_slot, raw_text, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                pasto,
                mood_score,
                _serialize_habits(habits_done),
                note_salute,
                1 if attivita_fisica else (0 if attivita_fisica is False else None),
                minuti_attivita,
                checkin_slot,
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
        if item.get("attivita_fisica") is not None:
            bits.append(f"attivita={item['attivita_fisica']}")
        if item.get("minuti_attivita") is not None:
            bits.append(f"min_att={item['minuti_attivita']}")
        if item.get("note_salute"):
            bits.append(f"note={item['note_salute']}")
        lines.append(" | ".join(bits))
    return "\n".join(lines)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["habits_done"] = _deserialize_habits(data.get("habits_done"))
    if data.get("attivita_fisica") is not None:
        data["attivita_fisica"] = bool(data["attivita_fisica"])
    return data
