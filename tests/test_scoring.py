"""Tests for the deterministic ground-truth scoring rule (ml/scoring.py)."""
from ml.scoring import score_app


def test_minimal_scopes_are_low_risk():
    result = score_app("Flashcard / Quiz Tool", ["openid", "userinfo.email", "userinfo.profile"])
    assert result.tier == "Low"
    assert result.score < 35


def test_full_drive_and_gmail_is_high_risk():
    result = score_app(
        "Digital Whiteboard",
        ["openid", "userinfo.email", "drive", "gmail.modify"],
    )
    assert result.tier == "High"


def test_category_mismatch_is_penalized():
    """A quiz app requesting gmail.send is an outlier for its category and
    should score meaningfully higher than the same scope count with no
    category mismatch."""
    matched = score_app("Parent Communication App",  # gmail.send is *expected* here
                         ["openid", "userinfo.email", "userinfo.profile", "gmail.send"])
    mismatched = score_app("Flashcard / Quiz Tool",  # gmail.send is an outlier here
                            ["openid", "userinfo.email", "userinfo.profile", "gmail.send"])
    assert mismatched.score > matched.score


def test_dangerous_combo_is_flagged():
    result = score_app(
        "Flashcard / Quiz Tool",
        ["openid", "userinfo.email", "contacts.readonly", "gmail.send"],
    )
    assert len(result.tripped_combos) >= 1
    assert result.tier in ("Medium", "High")


def test_score_is_bounded_0_to_100():
    # Deliberately pile on every restricted scope + every dangerous combo.
    result = score_app(
        "Reading / Library App",
        ["gmail.readonly", "gmail.modify", "drive", "contacts",
         "classroom.student-submissions.students.readonly",
         "admin.directory.user.readonly", "contacts.readonly", "gmail.send"],
    )
    assert 0.0 <= result.score <= 100.0


def test_unrecognized_scopes_are_ignored_not_crashing():
    result = score_app("Flashcard / Quiz Tool", ["openid", "not.a.real.scope"])
    assert result.tier in ("Low", "Medium", "High")


def test_no_recognized_scopes_is_zero():
    result = score_app("Flashcard / Quiz Tool", ["not.a.real.scope"])
    assert result.score == 0.0
    assert result.tier == "Low"


def test_omitting_publisher_metadata_matches_scope_only_score():
    """Backward compatibility: a caller that never mentions publisher trust
    (e.g. Assessment Mode fed a bare scope list) gets exactly the old,
    scope-only behavior -- the trust term contributes nothing when unknown."""
    scopes = ["openid", "userinfo.email", "drive", "gmail.modify"]
    bare = score_app("Digital Whiteboard", scopes)
    explicit_none = score_app("Digital Whiteboard", scopes,
                               publisher_verified=None, account_age_days=None, install_count=None)
    assert bare.score == explicit_none.score
    assert bare.tier == explicit_none.tier


def test_trustworthy_publisher_discounts_same_risky_scopes():
    """The whole point of the upgrade: identical scopes score differently
    depending on real-world publisher trust context -- a static per-scope
    table has no field for this at all."""
    scopes = ["openid", "userinfo.email", "userinfo.profile", "drive.file", "contacts.readonly", "gmail.send"]
    trusted = score_app("Flashcard / Quiz Tool", scopes,
                         publisher_verified=True, account_age_days=2500, install_count=50000)
    shady = score_app("Flashcard / Quiz Tool", scopes,
                       publisher_verified=False, account_age_days=15, install_count=40)
    assert shady.score > trusted.score


def test_trust_context_is_moot_with_no_recognized_scopes():
    """Nothing to weigh means publisher trust can't matter either -- both
    hit the same early return regardless of how shady or trustworthy the
    (irrelevant) publisher looks."""
    trusted = score_app("Flashcard / Quiz Tool", ["not.a.real.scope"],
                         publisher_verified=True, account_age_days=2500, install_count=50000)
    shady = score_app("Flashcard / Quiz Tool", ["not.a.real.scope"],
                       publisher_verified=False, account_age_days=15, install_count=40)
    assert trusted.score == shady.score == 0.0
