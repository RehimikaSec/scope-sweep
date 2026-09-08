"""
Feature engineering: turns a (category, scope_list) pair into the numeric
feature vector the ML model actually trains and predicts on.

Deliberately NOT fed the ground-truth scoring formula's output -- the model
never sees ml/scoring.py's numbers during inference. It only sees these
engineered features and has to learn, from labeled examples, how they relate
to risk. This is the difference between "the model memorized the rule" and
"the model learned a generalizable approximation of the rule," and it's why
a held-out test-set accuracy score (see ml/model.py) is a meaningful number
rather than a foregone conclusion.
"""

from __future__ import annotations

from data.scopes_reference import SCOPES, TIER_WEIGHT, DANGEROUS_COMBOS
from data.categories_reference import CATEGORIES

FEATURE_NAMES = [
    "n_scopes",
    "n_recommended",
    "n_sensitive",
    "n_restricted",
    "max_tier_weight",
    "sum_tier_weight",
    "n_unexpected_for_category",
    "unexpected_weight_sum",
    "n_dangerous_combos",
    "category_baseline_sensitivity",
]


def _category_baseline(category: str) -> float:
    cat = CATEGORIES.get(category)
    if not cat:
        return 0.0
    return sum(TIER_WEIGHT[SCOPES[s]["tier"]] for s in cat["expected"] if s in SCOPES)


def extract_features(category: str, scope_ids: list[str]) -> list[float]:
    scope_set = set(scope_ids)
    weights = [TIER_WEIGHT[SCOPES[s]["tier"]] for s in scope_ids if s in SCOPES]

    n_recommended = sum(1 for s in scope_ids if s in SCOPES and SCOPES[s]["tier"] == "recommended")
    n_sensitive = sum(1 for s in scope_ids if s in SCOPES and SCOPES[s]["tier"] == "sensitive")
    n_restricted = sum(1 for s in scope_ids if s in SCOPES and SCOPES[s]["tier"] == "restricted")

    cat = CATEGORIES.get(category)
    if cat:
        allowed = set(cat["expected"]) | set(cat["plausible_extra"])
        unexpected = scope_set - allowed
    else:
        unexpected = scope_set
    unexpected_weight_sum = sum(TIER_WEIGHT[SCOPES[s]["tier"]] for s in unexpected if s in SCOPES)

    n_combos = sum(1 for combo, _ in DANGEROUS_COMBOS if combo.issubset(scope_set))

    return [
        float(len(scope_ids)),
        float(n_recommended),
        float(n_sensitive),
        float(n_restricted),
        float(max(weights) if weights else 0),
        float(sum(weights)),
        float(len(unexpected)),
        float(unexpected_weight_sum),
        float(n_combos),
        float(_category_baseline(category)),
    ]
