"""End-to-end tests against the FastAPI app, using an isolated temp database
so this test run never touches (or gets order-dependent on) the real
data/scopesweep.db file a human demo session would create.
"""
import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from backend import game_state
    monkeypatch.setattr(game_state, "DB_PATH", tmp_path / "test_scopesweep.db")

    from backend import app as app_module
    importlib.reload(app_module)
    return TestClient(app_module.app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_full_game_round_trip(client):
    r = client.post("/api/session", json={"player_name": "Tester"})
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    r = client.get("/api/round", params={"session_id": session_id})
    assert r.status_code == 200
    round_data = r.json()
    assert round_data["app_id"]
    assert len(round_data["scopes"]) > 0
    assert "publisher" in round_data
    assert set(round_data["publisher"].keys()) == {"verified", "account_age_days", "install_count"}

    r = client.post("/api/guess", json={
        "session_id": session_id, "app_id": round_data["app_id"], "guess_tier": "Medium",
    })
    assert r.status_code == 200
    result = r.json()
    assert result["ground_truth_tier"] in ("Low", "Medium", "High")
    assert result["session"]["rounds_played"] == 1


def test_guess_rejects_unknown_session(client):
    r = client.post("/api/guess", json={
        "session_id": "does-not-exist", "app_id": "app-001", "guess_tier": "Low",
    })
    assert r.status_code == 404


def test_guess_rejects_invalid_tier(client):
    r = client.post("/api/session", json={"player_name": "Tester"})
    session_id = r.json()["session_id"]
    r = client.get("/api/round", params={"session_id": session_id})
    app_id = r.json()["app_id"]

    r = client.post("/api/guess", json={
        "session_id": session_id, "app_id": app_id, "guess_tier": "Extreme",
    })
    assert r.status_code == 400


def test_leaderboard_reflects_played_sessions(client):
    r = client.post("/api/session", json={"player_name": "Alice"})
    session_id = r.json()["session_id"]
    r = client.get("/api/round", params={"session_id": session_id})
    app_id = r.json()["app_id"]
    client.post("/api/guess", json={"session_id": session_id, "app_id": app_id, "guess_tier": "Low"})

    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    names = [e["player_name"] for e in r.json()["entries"]]
    assert "Alice" in names


def test_model_stats_endpoint(client):
    r = client.get("/api/model/stats")
    assert r.status_code == 200
    data = r.json()
    assert 0.0 <= data["holdout_accuracy"] <= 1.0
    assert len(data["feature_importances"]) == len(data["feature_names"])


def test_assess_endpoint_ranks_results_worst_first(client):
    r = client.post("/api/assess", json={"apps": [
        {"name": "Boring App", "category": "Digital Whiteboard",
         "scopes": ["openid", "userinfo.email"]},
        {"name": "Scary App", "category": "Digital Whiteboard",
         "scopes": ["openid", "drive", "gmail.modify", "contacts", "admin.directory.user.readonly"]},
    ]})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["name"] == "Scary App"
    assert results[0]["model_score"] >= results[1]["model_score"]


def test_assess_uses_publisher_context_when_provided(client):
    scopes = ["openid", "userinfo.email", "userinfo.profile", "drive.file", "contacts.readonly", "gmail.send"]
    r = client.post("/api/assess", json={"apps": [
        {"name": "Trusted App", "category": "Flashcard / Quiz Tool", "scopes": scopes,
         "publisher_verified": True, "account_age_days": 2500, "install_count": 50000},
        {"name": "Shady App", "category": "Flashcard / Quiz Tool", "scopes": scopes,
         "publisher_verified": False, "account_age_days": 15, "install_count": 40},
        {"name": "No Context App", "category": "Flashcard / Quiz Tool", "scopes": scopes},
    ]})
    assert r.status_code == 200
    results = {row["name"]: row for row in r.json()["results"]}
    assert results["Trusted App"]["had_publisher_context"] is True
    assert results["Shady App"]["had_publisher_context"] is True
    assert results["No Context App"]["had_publisher_context"] is False
    assert results["Shady App"]["model_score"] >= results["Trusted App"]["model_score"]


def test_assess_handles_unrecognized_scopes_gracefully(client):
    r = client.post("/api/assess", json={"apps": [
        {"name": "Weird App", "category": "Digital Whiteboard", "scopes": ["not.a.real.scope"]},
    ]})
    assert r.status_code == 200
    assert r.json()["results"][0]["unrecognized_scopes"] == ["not.a.real.scope"]


def test_index_serves_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ScopeSweep" in r.text


def test_sweep_today_is_deterministic_and_shareable(client):
    r1 = client.get("/api/sweep/today")
    r2 = client.get("/api/sweep/today")
    assert r1.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["date"] == d2["date"]
    assert d1["day_number"] == d2["day_number"]
    assert d1["day_number"] >= 1
    assert len(d1["rounds"]) == 10
    # Same date -> same 10 apps in the same order for everyone who plays today.
    assert [r["app_id"] for r in d1["rounds"]] == [r["app_id"] for r in d2["rounds"]]


def test_sweep_guess_is_tagged_with_mode_and_date(client):
    sweep = client.get("/api/sweep/today").json()
    session_id = client.post("/api/session", json={"player_name": "Sweeper"}).json()["session_id"]
    app_id = sweep["rounds"][0]["app_id"]

    r = client.post("/api/guess", json={
        "session_id": session_id, "app_id": app_id, "guess_tier": "Medium",
        "mode": "sweep", "sweep_date": sweep["date"],
    })
    assert r.status_code == 200


def test_community_stats_empty_before_any_guesses(client):
    r = client.get("/api/community-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_guesses"] == 0
    assert data["human_accuracy"] is None


def test_community_stats_aggregates_after_guesses(client):
    session_id = client.post("/api/session", json={"player_name": "Alice"}).json()["session_id"]
    round_data = client.get("/api/round", params={"session_id": session_id}).json()
    client.post("/api/guess", json={
        "session_id": session_id, "app_id": round_data["app_id"], "guess_tier": "Low",
    })

    r = client.get("/api/community-stats")
    data = r.json()
    assert data["total_guesses"] == 1
    assert data["human_accuracy"] in (0.0, 1.0)
    assert data["human_wins"] + data["model_wins"] + data["ties"] == 1
