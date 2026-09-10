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
    mode TEXT NOT NULL DEFAULT 'practice',
    sweep_date TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Lightweight migration for DBs created before mode/sweep_date existed --
    # SQLite has no "ADD COLUMN IF NOT EXISTS", so we probe and ignore.
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(guesses)")}
    if "mode" not in existing_cols:
        conn.execute("ALTER TABLE guesses ADD COLUMN mode TEXT NOT NULL DEFAULT 'practice'")
    if "sweep_date" not in existing_cols:
        conn.execute("ALTER TABLE guesses ADD COLUMN sweep_date TEXT")
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
                  ground_truth_tier: str, model_tier: str, model_score: float,
                  mode: str = "practice", sweep_date: str | None = None) -> dict:
    is_correct = int(guess_tier == ground_truth_tier)
    model_agreed = int(model_tier == ground_truth_tier)

    conn = _connect()
    with conn:
        conn.execute(
            """INSERT INTO guesses
               (session_id, app_id, category, guess_tier, ground_truth_tier,
                model_tier, model_score, is_correct, model_agreed_with_truth,
                mode, sweep_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, app_id, category, guess_tier, ground_truth_tier,
             model_tier, model_score, is_correct, model_agreed, mode, sweep_date, _now()),
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


def community_stats() -> dict:
    """Aggregate, across every guess ever logged by anyone, the live
    'humans vs. the model' record this project's whole AI pitch rests on --
    not a claim, a number anyone can watch update as more people play.
    """
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) AS n FROM guesses").fetchone()["n"]
    if total == 0:
        conn.close()
        return {
            "total_guesses": 0, "human_accuracy": None, "model_accuracy": None,
            "human_wins": 0, "model_wins": 0, "ties": 0, "most_disputed_apps": [],
        }

    human_correct = conn.execute(
        "SELECT COUNT(*) AS n FROM guesses WHERE is_correct = 1"
    ).fetchone()["n"]
    model_correct = conn.execute(
        "SELECT COUNT(*) AS n FROM guesses WHERE model_agreed_with_truth = 1"
    ).fetchone()["n"]

    # Head-to-head: for each guess, did the human get it right where the
    # model didn't (human win), the reverse (model win), or did they match?
    human_wins = conn.execute(
        "SELECT COUNT(*) AS n FROM guesses WHERE is_correct = 1 AND model_agreed_with_truth = 0"
    ).fetchone()["n"]
    model_wins = conn.execute(
        "SELECT COUNT(*) AS n FROM guesses WHERE is_correct = 0 AND model_agreed_with_truth = 1"
    ).fetchone()["n"]
    ties = total - human_wins - model_wins

    # Apps where players most often disagree with each other -- a genuine
    # signal for scripts/analyze_guesses.py and for the community tab.
    disputed = conn.execute(
        """SELECT app_id, category, COUNT(DISTINCT guess_tier) AS n_distinct_guesses,
                  COUNT(*) AS n_guesses
           FROM guesses
           GROUP BY app_id
           HAVING n_guesses >= 2 AND n_distinct_guesses >= 2
           ORDER BY n_distinct_guesses DESC, n_guesses DESC
           LIMIT 5"""
    ).fetchall()
    conn.close()

    return {
        "total_guesses": total,
        "human_accuracy": round(human_correct / total, 3),
        "model_accuracy": round(model_correct / total, 3),
        "human_wins": human_wins,
        "model_wins": model_wins,
        "ties": ties,
        "most_disputed_apps": [dict(r) for r in disputed],
    }
