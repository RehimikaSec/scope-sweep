"""
Turns the accumulated guess log into a small report -- and, this is the
point, into a labeled CSV a real retraining pass could use.

This is the concrete version of the "games with a purpose" pitch: every
round anyone plays is one human judgment on one real scope combination. In
a real deployment, once enough of these accumulate you'd:
  1. Compute human/human agreement per app (inter-rater agreement) to find
     which scope combinations people genuinely find ambiguous -- those are
     exactly the cases worth a security team's manual review.
  2. Compare human-majority-vote labels against the model's own prediction
     to find where the model is confidently *wrong*.
  3. Fold high-agreement human labels back into a retraining set -- moving
     the model off a purely rule-derived dataset (see ml/scoring.py) and
     onto real human judgment, which is the whole reason the label source
     matters for a "real AI" story rather than a hand-written formula in a
     costume.

For a semester-length pilot, this script is the honest MVP of that idea:
it reads what's actually in the local SQLite guess log and reports on it.
A live active-learning retraining loop is future work, noted here and in
the README rather than pretended into existence.

Run with:  python3 -m scripts.analyze_guesses
"""
from __future__ import annotations
import csv
import sys
from collections import defaultdict
from pathlib import Path

from backend import game_state


def main():
    guesses = game_state.all_guesses()
    if not guesses:
        print("No guesses recorded yet -- play a few rounds first "
              "(uvicorn backend.app:app, then open http://127.0.0.1:8000).")
        return

    print(f"Total guesses logged: {len(guesses)}\n")

    # Per-app aggregation: how many humans agreed with each other, and with
    # the ground truth / model.
    by_app: dict[str, list[dict]] = defaultdict(list)
    for g in guesses:
        by_app[g["app_id"]].append(g)

    ambiguous = []
    model_wrong_confident = []

    for app_id, rows in by_app.items():
        tier_votes = defaultdict(int)
        for r in rows:
            tier_votes[r["guess_tier"]] += 1
        majority_tier, majority_count = max(tier_votes.items(), key=lambda kv: kv[1])
        agreement_rate = majority_count / len(rows)

        ground_truth = rows[0]["ground_truth_tier"]
        model_tier = rows[0]["model_tier"]

        if agreement_rate < 0.7 and len(rows) >= 3:
            ambiguous.append((app_id, rows[0]["category"], tier_votes, agreement_rate))

        if model_tier != ground_truth:
            model_wrong_confident.append((app_id, rows[0]["category"], model_tier, ground_truth))

    print("=== Apps where human players disagreed with each other most (n>=3 guesses) ===")
    if ambiguous:
        for app_id, cat, votes, rate in sorted(ambiguous, key=lambda x: x[3]):
            print(f"  {app_id} ({cat}): {dict(votes)}  -- {rate:.0%} agreed on the majority pick")
    else:
        print("  (not enough guesses per app yet to compute this -- keep playing)")

    print("\n=== Apps where the model's own call disagreed with ground truth ===")
    seen = set()
    for app_id, cat, model_tier, truth in model_wrong_confident:
        if app_id in seen:
            continue
        seen.add(app_id)
        print(f"  {app_id} ({cat}): model said {model_tier}, ground truth is {truth}")
    if not seen:
        print("  (none in this run)")

    # Export the raw guess log as a candidate retraining CSV.
    out_path = Path(__file__).parent.parent / "data" / "guess_log_export.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(guesses[0].keys()))
        writer.writeheader()
        writer.writerows(guesses)
    print(f"\nExported full guess log to {out_path} "
          f"({len(guesses)} rows) -- this is the raw material for a future "
          f"human-labeled retraining pass.")


if __name__ == "__main__":
    sys.exit(main() or 0)
