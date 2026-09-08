"""Tests for feature engineering (ml/features.py)."""
from ml.features import extract_features, FEATURE_NAMES


def test_feature_vector_length_matches_names():
    feats = extract_features("Flashcard / Quiz Tool", ["openid", "userinfo.email"])
    assert len(feats) == len(FEATURE_NAMES)


def test_more_scopes_increase_n_scopes_feature():
    idx = FEATURE_NAMES.index("n_scopes")
    small = extract_features("Flashcard / Quiz Tool", ["openid"])
    big = extract_features("Flashcard / Quiz Tool", ["openid", "userinfo.email", "drive"])
    assert big[idx] > small[idx]


def test_restricted_scope_increases_max_tier_weight():
    idx = FEATURE_NAMES.index("max_tier_weight")
    low = extract_features("Flashcard / Quiz Tool", ["openid"])
    high = extract_features("Flashcard / Quiz Tool", ["openid", "drive"])  # drive = restricted
    assert high[idx] > low[idx]


def test_unrecognized_scope_does_not_crash_and_contributes_zero_weight():
    feats = extract_features("Flashcard / Quiz Tool", ["not.a.real.scope"])
    assert len(feats) == len(FEATURE_NAMES)


def test_unknown_category_treats_all_scopes_as_unexpected():
    idx = FEATURE_NAMES.index("n_unexpected_for_category")
    feats = extract_features("Not A Real Category", ["openid", "drive"])
    assert feats[idx] == 2.0
