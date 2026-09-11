"""Tests for feature engineering (ml/features.py)."""
from ml.features import extract_features, compute_population_stats, FEATURE_NAMES


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


def test_missing_metadata_uses_distinct_unknown_sentinel():
    """When publisher metadata isn't supplied, the contextual features get
    a -1 sentinel -- distinguishable from any real value -- rather than a
    silently guessed default."""
    feats = extract_features("Flashcard / Quiz Tool", ["openid"])
    for name in ("publisher_verified", "account_age_norm", "install_count_log"):
        assert feats[FEATURE_NAMES.index(name)] == -1.0


def test_supplied_metadata_populates_contextual_features():
    feats = extract_features(
        "Flashcard / Quiz Tool", ["openid"],
        metadata={"publisher_verified": True, "account_age_days": 900, "install_count": 5000},
    )
    assert feats[FEATURE_NAMES.index("publisher_verified")] == 1.0
    assert 0.0 < feats[FEATURE_NAMES.index("account_age_norm")] <= 1.0
    assert feats[FEATURE_NAMES.index("install_count_log")] > 0.0


def test_unexpected_scope_rarity_reflects_population_frequency():
    """A scope that's common in this category's population (in the corpus
    passed to compute_population_stats) should be treated as less 'rare'
    than one that has never appeared for this category -- this is a
    statistic about the whole dataset, not a single app."""
    category = "Flashcard / Quiz Tool"
    apps = (
        [{"category": category, "scopes": ["openid", "gmail.send"]}] * 8
        + [{"category": category, "scopes": ["openid"]}] * 2
    )
    stats = compute_population_stats(apps)
    idx = FEATURE_NAMES.index("unexpected_scope_rarity")

    common_outlier = extract_features(category, ["openid", "gmail.send"], population_stats=stats)
    never_seen_outlier = extract_features(category, ["openid", "contacts"], population_stats=stats)
    assert never_seen_outlier[idx] > common_outlier[idx]


def test_no_population_stats_defaults_rarity_to_zero():
    idx = FEATURE_NAMES.index("unexpected_scope_rarity")
    feats = extract_features("Flashcard / Quiz Tool", ["openid", "gmail.send"])
    assert feats[idx] == 0.0
