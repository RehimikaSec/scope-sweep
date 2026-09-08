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
