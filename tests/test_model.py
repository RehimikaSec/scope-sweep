"""Tests for the trained ML model (ml/model.py).

These are intentionally about *behavior and honesty*, not about hitting an
exact accuracy number -- a synthetic dataset's exact accuracy will drift
slightly if anyone tweaks data/generate_dataset.py, and pinning to a single
decimal would make this test brittle for the wrong reason.
"""
from ml.model import ScopeRiskModel


def test_model_trains_and_reports_honest_holdout_metrics():
    model = ScopeRiskModel()
    assert 0.0 <= model.holdout_accuracy <= 1.0
    assert model.n_train > 0
    assert model.n_test > 0
    assert model.n_train + model.n_test == len(model.apps)


def test_predict_returns_valid_tier_and_probabilities():
    model = ScopeRiskModel()
    pred = model.predict("Flashcard / Quiz Tool", ["openid", "userinfo.email"])
    assert pred.tier in ("Low", "Medium", "High")
    assert 0.0 <= pred.score_0_100 <= 100.0
    assert abs(sum(pred.probabilities.values()) - 1.0) < 0.01
    assert set(pred.probabilities.keys()) == {"Low", "Medium", "High"}


def test_more_sensitive_scopes_generally_score_higher():
    model = ScopeRiskModel()
    low = model.predict("Flashcard / Quiz Tool", ["openid", "userinfo.email"])
    high = model.predict("Flashcard / Quiz Tool",
                          ["openid", "userinfo.email", "drive", "gmail.modify", "contacts"])
    assert high.score_0_100 > low.score_0_100


def test_feature_importances_sum_close_to_one_and_are_non_negative():
    model = ScopeRiskModel()
    total = sum(imp for _, imp in model.feature_importances)
    assert abs(total - 1.0) < 0.01
    assert all(imp >= 0 for _, imp in model.feature_importances)


def test_top_features_returned_for_a_prediction():
    model = ScopeRiskModel()
    pred = model.predict("Flashcard / Quiz Tool", ["openid", "drive", "gmail.modify"])
    assert len(pred.top_features) == 3
    for name, val in pred.top_features:
        assert isinstance(name, str)


def test_predict_works_with_and_without_publisher_metadata():
    """The model must degrade gracefully when metadata isn't available
    (e.g. a real district export with no publisher trust data) -- it
    should still return a valid prediction, just without that signal."""
    model = ScopeRiskModel()
    scopes = ["openid", "userinfo.email", "drive", "contacts.readonly", "gmail.send"]
    bare = model.predict("Flashcard / Quiz Tool", scopes)
    with_context = model.predict(
        "Flashcard / Quiz Tool", scopes,
        metadata={"publisher_verified": True, "account_age_days": 2000, "install_count": 40000},
    )
    assert bare.tier in ("Low", "Medium", "High")
    assert with_context.tier in ("Low", "Medium", "High")


def test_population_stats_computed_at_load_time():
    model = ScopeRiskModel()
    assert isinstance(model.population_stats, dict)
    assert len(model.population_stats) > 0
