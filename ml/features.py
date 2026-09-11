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
import math
from collections import defaultdict

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
    # -- Contextual / publisher-trust features. -1 is a distinct "unknown"
    # sentinel (never a legitimate value for these), so the model can learn
    # a different branch for "no metadata supplied" instead of us silently
    # guessing a fake default.
    "publisher_verified",
    "account_age_norm",
    "install_count_log",
    # -- Population-derived anomaly feature. This one is fundamentally NOT
    # something a static per-app lookup table could express: it depends on
    # the empirical frequency of this app's unusual scopes across every
    # OTHER app in its category, computed from the full corpus. A rule that
    # only looks at one app at a time cannot produce this number.
    "unexpected_scope_rarity",
]


def _category_baseline(category: str) -> float:
    cat = CATEGORIES.get(category)
    if not cat:
        return 0.0
    return sum(TIER_WEIGHT[SCOPES[s]["tier"]] for s in cat["expected"] if s in SCOPES)


def compute_population_stats(apps: list[dict]) -> dict[str, dict[str, float]]:
    """Empirical frequency of each scope within each category, computed
    once from the full training corpus. This is what makes
    `unexpected_scope_rarity` a genuinely population-derived statistic
    rather than something hand-codeable per app: it can only be computed
    with the whole dataset in hand, and it changes as the dataset does.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[str, int] = defaultdict(int)
    for a in apps:
        totals[a["category"]] += 1
        for s in a.get("scopes", []):
            counts[a["category"]][s] += 1
    return {
        cat: {s: counts[cat][s] / totals[cat] for s in counts[cat]}
        for cat in totals
    }


def _scope_rarity(category: str, unexpected: set[str],
                   population_stats: dict[str, dict[str, float]] | None) -> float:
    if not unexpected or not population_stats:
        return 0.0
    freqs = population_stats.get(category, {})
    # 1 - frequency = "how unfamiliar is this scope for this category,
    # historically" -- a scope this category's population has never
    # requested before scores a full 1.0.
    unfamiliarity = [1.0 - freqs.get(s, 0.0) for s in unexpected]
    return sum(unfamiliarity) / len(unfamiliarity)


def extract_features(category: str, scope_ids: list[str], *,
                      metadata: dict | None = None,
                      population_stats: dict | None = None) -> list[float]:
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

    # Contextual publisher-trust features. -1 is a distinct "unknown"
    # sentinel, never a real value these features could otherwise take.
    if metadata and all(k in metadata and metadata[k] is not None for k in
                         ("publisher_verified", "account_age_days", "install_count")):
        publisher_verified_feat = 1.0 if metadata["publisher_verified"] else 0.0
        account_age_norm = min(float(metadata["account_age_days"]), 3000.0) / 3000.0
        install_count_log = math.log10(max(float(metadata["install_count"]), 0.0) + 1.0)
    else:
        publisher_verified_feat = -1.0
        account_age_norm = -1.0
        install_count_log = -1.0

    rarity = _scope_rarity(category, unexpected, population_stats)

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
        publisher_verified_feat,
        account_age_norm,
        install_count_log,
        float(rarity),
    ]
