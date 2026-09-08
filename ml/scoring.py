"""
Ground-truth risk scoring rule.

This is the deterministic, documented "answer key" used to label the
synthetic training data. It is deliberately hand-written and auditable --
for a security tool, an opaque black-box label source would be a real
credibility problem, so every point of this formula is explainable.

The ML model in ml/model.py is NOT this function. It is trained on
*features* derived from a scope list and learns to approximate this
formula's output -- which lets it generalize to scope combinations that
never appeared in training data, and lets us honestly measure how well it
generalizes (see tests/test_model.py and ml/model.py's held-out accuracy).
"""

from __future__ import annotations
from dataclasses import dataclass, field

from data.scopes_reference import SCOPES, TIER_WEIGHT, DANGEROUS_COMBOS
from data.categories_reference import CATEGORIES


@dataclass
class RiskResult:
    score: float                 # 0-100 continuous risk score
    tier: str                    # "Low" / "Medium" / "High"
    reasons: list[str] = field(default_factory=list)
    tripped_combos: list[str] = field(default_factory=list)


def _tier_from_score(score: float) -> str:
    if score < 35:
        return "Low"
    if score < 62:
        return "Medium"
    return "High"


def score_app(category: str, scope_ids: list[str]) -> RiskResult:
    """Compute the ground-truth risk score/tier for a given app category
    and its requested scope list. Every contribution is logged in `reasons`
    so the game can show a real explanation, not just a number.
    """
    reasons: list[str] = []
    scope_set = set(scope_ids)

    # 1. Base severity: driven by the single most sensitive scope requested,
    #    plus a smaller contribution from every additional sensitive/restricted
    #    scope (breadth matters, not just the worst single scope).
    weights = [TIER_WEIGHT[SCOPES[s]["tier"]] for s in scope_ids if s in SCOPES]
    if not weights:
        return RiskResult(score=0.0, tier="Low", reasons=["No recognized scopes requested."])

    max_weight = max(weights)
    breadth_bonus = sum(w for w in weights if w >= TIER_WEIGHT["sensitive"]) - max_weight
    base = max_weight * 9.0 + breadth_bonus * 2.5
    reasons.append(
        f"Most sensitive scope requested has weight {max_weight} "
        f"(tier scale: recommended=1, sensitive=3, restricted=6)."
    )

    # 2. Category-mismatch penalty: does this app request scopes well beyond
    #    what its declared category plausibly needs?
    cat = CATEGORIES.get(category)
    mismatch_bonus = 0.0
    if cat:
        allowed = set(cat["expected"]) | set(cat["plausible_extra"])
        unexpected = scope_set - allowed
        unexpected_weight = sum(
            TIER_WEIGHT[SCOPES[s]["tier"]] for s in unexpected if s in SCOPES
        )
        if unexpected:
            mismatch_bonus = unexpected_weight * 4.0
            reasons.append(
                f"Requests {len(unexpected)} scope(s) outside what a "
                f"'{category}' app typically needs: {', '.join(sorted(unexpected))}."
            )

    # 3. Dangerous-combination bonus: scopes that are individually moderate
    #    but materially riskier together.
    combo_bonus = 0.0
    tripped = []
    for combo, reason in DANGEROUS_COMBOS:
        if combo.issubset(scope_set):
            combo_bonus += 14.0
            tripped.append(reason)
    if tripped:
        reasons.append(f"{len(tripped)} dangerous scope combination(s) detected.")

    # 4. Blast-radius bonus: a handful of extra points per additional scope,
    #    since every additional grant is additional attack surface even if
    #    individually low-sensitivity.
    breadth_count_bonus = max(0, len(scope_ids) - 3) * 1.5

    raw = base + mismatch_bonus + combo_bonus + breadth_count_bonus
    # Saturating transform (raw / (raw + K)) instead of a hard clip, so a
    # handful of stacked bonuses spreads across the upper range instead of
    # every "bad" app flattening out at exactly 100.
    score = 100.0 * raw / (raw + 45.0)
    score = max(0.0, min(100.0, round(score, 1)))

    return RiskResult(
        score=round(score, 1),
        tier=_tier_from_score(score),
        reasons=reasons,
        tripped_combos=tripped,
    )
