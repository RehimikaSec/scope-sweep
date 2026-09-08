"""
Lightweight persistence for game sessions, the leaderboard, and every guess
ever made.

SQLite, not because the data is big (it isn't) but because the *guess log*
is the whole point of pairing gamification with the AI category: every
round a person plays produces one human-labeled judgment on a real scope
combination. scripts/analyze_guesses.py reads this same table to show how
that log becomes a candidate dataset for improving the model over time --
the "games with a purpose" pattern (in the lineage of the ESP Game /
reCAPTCHA) applied to security education instead of image labeling or OCR.
"""

from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass

DB_PATH = Path(__file__).parent.parent / "data" / "scopesweep.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    player_name TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0,
    rounds_played INTEGER NOT NULL DEFAULT 0,
    rounds_correct INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    app_id TEXT NOT NULL,
    category TEXT NOT NULL,
    guess_tier TEXT NOT NULL,
    ground_truth_tier TEXT NOT NULL,
    model_tier TEXT NOT NULL,
    model_score REAL NOT NULL,
    is_correct INTEGER NOT NULL,
    model_agreed_with_truth INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(player_name: str) -> str:
    session_id = str(uuid.uuid4())[:8]
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO sessions (id, player_name, created_at) VALUES (?, ?, ?)",
            (session_id, player_name.strip()[:40] or "Anonymous", _now()),
        )
    conn.close()
    return session_id


def get_session(session_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def record_guess(session_id: str, app_id: str, category: str, guess_tier: str,
                  ground_truth_tier: str, model_tier: str, model_score: float) -> dict:
    is_correct = int(guess_tier == ground_truth_tier)
    model_agreed = int(model_tier == ground_truth_tier)

    conn = _connect()
    with conn:
        conn.execute(
            """INSERT INTO guesses
               (session_id, app_id, category, guess_tier, ground_truth_tier,
                model_tier, model_score, is_correct, model_agreed_with_truth, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, app_id, category, guess_tier, ground_truth_tier,
             model_tier, model_score, is_correct, model_agreed, _now()),
        )
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if session is None:
            conn.close()
            raise ValueError(f"Unknown session {session_id}")

        new_streak = session["streak"] + 1 if is_correct else 0
        best_streak = max(session["best_streak"], new_streak)
        points = 0
        if is_correct:
            points = 10 + min(new_streak, 5) * 2  # streak bonus caps at +10

        conn.execute(
            """UPDATE sessions SET
                 score = score + ?,
                 streak = ?,
                 best_streak = ?,
                 rounds_played = rounds_played + 1,
                 rounds_correct = rounds_correct + ?
               WHERE id = ?""",
            (points, new_streak, best_streak, is_correct, session_id),
        )
        updated = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return {"points_earned": points, "session": dict(updated), "is_correct": bool(is_correct),
            "model_agreed_with_truth": bool(model_agreed)}


def leaderboard(limit: int = 10) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        """SELECT player_name, score, best_streak, rounds_played, rounds_correct, created_at
           FROM sessions
           WHERE rounds_played > 0
           ORDER BY score DESC, best_streak DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_guesses() -> list[dict]:
    """Used by scripts/analyze_guesses.py -- the human-computation label log."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM guesses ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]
