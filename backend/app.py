"""
ScopeSweep API.

Three families of endpoint, matching the three ways this project earns its
place across categories:

  /api/round, /api/guess, /api/session, /api/leaderboard
      -> Category 3: the game loop itself.

  /api/model/stats
      -> Category 2: exposes the actual, honestly-measured ML model behind
         the game, instead of asking anyone to take "there's AI in here" on
         faith.

  /api/assess
      -> Category 1: the same model, repurposed as a real bulk-scoring tool
         a school's one IT coordinator could point at their district's
         actual list of authorized apps and scopes.

Run with:  uvicorn backend.app:app --reload
Then open  http://127.0.0.1:8000/
"""

from __future__ import annotations
import random
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from data.scopes_reference import SCOPES
from ml.model import get_model
from ml.scoring import score_app
from ml.features import FEATURE_NAMES
from backend import game_state
from backend.schemas import (
    NewSessionRequest, NewSessionResponse, RoundResponse, GuessRequest,
    GuessResponse, AssessRequest, AssessResultItem,
)

app = FastAPI(title="ScopeSweep API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# In-memory "which apps has this session already seen" tracker, so a round
# doesn't repeat until the pool is exhausted. Session state that matters
# (score, streak, guess log) lives in SQLite; this is just round-shuffling.
_SESSION_SEEN: dict[str, set[str]] = {}

# Day 1 of the Daily Sweep. Day number shown to players counts up from here.
SWEEP_EPOCH = date(2026, 9, 10)
SWEEP_SIZE = 10


def _scope_detail(scope_id: str) -> dict:
    meta = SCOPES.get(scope_id, {"tier": "sensitive", "label": scope_id, "desc": "Unrecognized scope."})
    return {"id": scope_id, "label": meta["label"], "tier": meta["tier"], "desc": meta["desc"]}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/session", response_model=NewSessionResponse)
def new_session(req: NewSessionRequest):
    session_id = game_state.create_session(req.player_name)
    _SESSION_SEEN[session_id] = set()
    return {"session_id": session_id}


@app.get("/api/session/{session_id}")
def read_session(session_id: str):
    session = game_state.get_session(session_id)
    if not session:
        raise HTTPException(404, "Unknown session")
    return session


@app.get("/api/round", response_model=RoundResponse)
def get_round(session_id: str):
    model = get_model()
    if not game_state.get_session(session_id):
        raise HTTPException(404, "Unknown session -- call POST /api/session first")

    seen = _SESSION_SEEN.setdefault(session_id, set())
    unseen = [a for a in model.apps if a["id"] not in seen]
    if not unseen:
        seen.clear()
        unseen = model.apps

    app_row = random.choice(unseen)
    seen.add(app_row["id"])

    return {
        "app_id": app_row["id"],
        "name": app_row["name"],
        "category": app_row["category"],
        "description": app_row["description"],
        "scopes": [_scope_detail(s) for s in app_row["scopes"]],
    }


@app.post("/api/guess", response_model=GuessResponse)
def submit_guess(req: GuessRequest):
    model = get_model()
    app_row = next((a for a in model.apps if a["id"] == req.app_id), None)
    if not app_row:
        raise HTTPException(404, "Unknown app_id")
    if req.guess_tier not in ("Low", "Medium", "High"):
        raise HTTPException(400, "guess_tier must be Low, Medium, or High")
    if not game_state.get_session(req.session_id):
        raise HTTPException(404, "Unknown session")

    prediction = model.predict(app_row["category"], app_row["scopes"])

    outcome = game_state.record_guess(
        session_id=req.session_id,
        app_id=app_row["id"],
        category=app_row["category"],
        guess_tier=req.guess_tier,
        ground_truth_tier=app_row["ground_truth_tier"],
        model_tier=prediction.tier,
        model_score=prediction.score_0_100,
        mode=req.mode,
        sweep_date=req.sweep_date,
    )

    return {
        "is_correct": outcome["is_correct"],
        "points_earned": outcome["points_earned"],
        "ground_truth_tier": app_row["ground_truth_tier"],
        "ground_truth_score": app_row["ground_truth_score"],
        "model_tier": prediction.tier,
        "model_score": prediction.score_0_100,
        "model_agreed_with_truth": outcome["model_agreed_with_truth"],
        "model_probabilities": prediction.probabilities,
        "reasons": app_row["reasons"],
        "tripped_combos": app_row["tripped_combos"],
        "top_model_features": [{"feature": n, "value": v} for n, v in prediction.top_features],
        "session": outcome["session"],
    }


@app.get("/api/leaderboard")
def get_leaderboard(limit: int = 10):
    return {"entries": game_state.leaderboard(limit)}


@app.get("/api/sweep/today")
def sweep_today():
    """The Daily Sweep: a fixed set of 10 apps, deterministically chosen from
    today's calendar date, so every player sees the exact same 10 rounds in
    the exact same order on a given day -- the whole reason it's shareable
    and comparable, the same trick behind Wordle's daily puzzle.
    """
    model = get_model()
    today = date.today()
    day_number = (today - SWEEP_EPOCH).days + 1
    rng = random.Random(today.isoformat())
    chosen = rng.sample(model.apps, k=min(SWEEP_SIZE, len(model.apps)))

    rounds = [{
        "app_id": a["id"],
        "name": a["name"],
        "category": a["category"],
        "description": a["description"],
        "scopes": [_scope_detail(s) for s in a["scopes"]],
    } for a in chosen]

    return {"date": today.isoformat(), "day_number": max(day_number, 1), "rounds": rounds}


@app.get("/api/community-stats")
def community_stats():
    """The live, growing 'humans vs. the model' scoreboard -- built from
    every guess anyone has ever logged, not a static claim.
    """
    return game_state.community_stats()


@app.get("/api/model/stats")
def model_stats():
    model = get_model()
    return {
        "holdout_accuracy": model.holdout_accuracy,
        "holdout_report": model.holdout_report,
        "n_train": model.n_train,
        "n_test": model.n_test,
        "feature_importances": [{"feature": n, "importance": round(float(i), 4)}
                                 for n, i in model.feature_importances],
        "feature_names": FEATURE_NAMES,
        "n_apps_total": len(model.apps),
    }


@app.get("/api/scopes")
def list_scopes():
    return {sid: meta for sid, meta in SCOPES.items()}


@app.post("/api/assess")
def assess(req: AssessRequest):
    """The Category-1 'real tool' mode: score an arbitrary list of
    (name, category, scopes) apps -- e.g. a district's actual authorized
    app export -- with the same model the game uses, ranked worst-first.
    """
    model = get_model()
    results: list[AssessResultItem] = []
    for a in req.apps:
        recognized = [s for s in a.scopes if s in SCOPES]
        unrecognized = [s for s in a.scopes if s not in SCOPES]
        prediction = model.predict(a.category, recognized)
        rule_result = score_app(a.category, recognized)
        results.append(AssessResultItem(
            name=a.name,
            category=a.category,
            scopes=a.scopes,
            model_tier=prediction.tier,
            model_score=prediction.score_0_100,
            reasons=rule_result.reasons,
            unrecognized_scopes=unrecognized,
        ))
    results.sort(key=lambda r: r.model_score, reverse=True)
    return {"results": [r.model_dump() for r in results]}


# --- Static frontend -------------------------------------------------------
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
