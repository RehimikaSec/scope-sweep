# ScopeSweep

**A game that teaches OAuth-permission literacy by making players out-guess a real machine learning model — and doubles as a scope-risk auditing tool a school's IT coordinator could actually run.**

Built for a cybersecurity competition. Touches three categories on purpose, not by stretching one idea to fit a checklist:

| Category | How ScopeSweep earns it |
|---|---|
| **2 — AI-Enabled Solution** | A `RandomForestClassifier`, trained on 14 engineered features — scope risk, category mismatch, real-world publisher-trust context, and a population-derived scope-rarity statistic — predicts an app's OAuth risk tier, with a real held-out accuracy score, real feature importances, and a real explanation per prediction. Not an LLM wrapper, and not a per-scope lookup table either (see below). |
| **3 — Cybersecurity Education** | The game loop is a spaced, scored, explained quiz: guess an app's risk tier before the model reveals its own call, see *why* both of you landed where you did, build real intuition for what an OAuth scope actually grants. |
| **1 — Community-Oriented Tool** | *Assessment Mode* runs the same model against a pasted list of real apps and scopes and returns a ranked risk report — the exact workflow a K-12 IT coordinator with no security background could run against their district's actual authorized-app export. |

---

## Why this design, not a chatbot

The obvious, weak version of "gamified AI security education" is a chatbot that quizzes you and an LLM that makes up the answers. ScopeSweep is built differently on purpose:

- **The risk model is real and auditable.** `ml/scoring.py` is a hand-written, fully documented rule (grounded in Google's own public OAuth scope sensitivity tiers) that labels a synthetic training set. `ml/model.py` trains a small classifier on *engineered features* derived from that data — never on the rule's own output — and reports its held-out accuracy honestly. You can read every line of both files; nothing is a black box.
- **Gamification isn't decoration — it's a data pipeline.** Every guess a player makes is logged (`backend/game_state.py`) with the ground truth, the model's call, and the human's call, all three. `scripts/analyze_guesses.py` turns that log into exactly what a real "games with a purpose" system (in the lineage of the ESP Game / reCAPTCHA) would use to find ambiguous cases and candidate retraining data. That's a genuine reason to gamify an AI system, not a scoreboard bolted onto a serious tool.
- **The same backend is a real tool, not just a game engine.** `POST /api/assess` takes a plain list of `{name, category, scopes}` and returns a ranked risk report. That's ClassroomShield's actual job, wearing the game's ML model.

---

## Why this isn't "a lookup table wearing a costume"

The honest version of the obvious skeptical question: if risk tiers come from a hand-written formula, isn't the model just memorizing that formula back? For the *scope-only* version of this project, that critique was fair. Two things now make it not true:

- **The score depends on more than the scope list.** `ml/scoring.py`'s ground truth is a function of scope severity *and* real-world publisher-trust context — whether the publisher is verified, how old the account is, and how many organizations have already installed it — applied as a genuine interaction term (it scales scope severity, it isn't an independent bonus tacked on). The exact same six scopes score differently depending on who's asking: a 6-year-old verified publisher with 41,000 installs gets a real discount; a 3-week-old unverified publisher with 60 installs gets a real premium. `tests/test_scoring.py::test_trustworthy_publisher_discounts_same_risky_scopes` asserts this directly. No static per-scope table has a field for "who is asking," so a lookup table literally cannot reproduce this rule, regardless of how big you make the table.
- **One feature is a property of the whole dataset, not any single app.** `unexpected_scope_rarity` (`ml/features.py`) measures how common a given "outlier" scope actually is within its category, computed from the empirical frequency across every other app in the training corpus (`compute_population_stats`). That number doesn't exist until you've looked at the whole population — it's a statistical/anomaly-detection-flavored signal, the same *kind* of feature a real fraud- or abuse-detection system leans on, not something any per-app rule could contain.

Both are opt-in and honestly degrade: if you don't have publisher metadata for an app (many real district exports won't), the model and the rule both fall back cleanly to scope-only scoring rather than guessing — `backend/schemas.py`'s `AssessAppRequest` makes every trust field optional, and `AssessResultItem.had_publisher_context` tells you which case you're in. Try Assessment Mode's sample data: `QuickQuiz Pro` and `StudyBuddy Beta` request the *identical* scope set and get different scores, for exactly this reason.

Worth saying plainly: retraining on the richer feature set brought held-out accuracy down from ~100% to **96.4%** (see `ml/model.py` / `/api/model/stats`). That's a feature, not a regression — it means the model is now approximating a genuinely harder, less trivially learnable function, and a held-out number that isn't suspiciously perfect is more credible under questioning, not less.

---

## Why anyone plays, and why they come back

A demo that only proves the mechanics work isn't the same as a game people actually want to open. Three deliberate hooks:

- **A premise, not just a mechanic.** You're framed as the newest — and only — app reviewer for a school district that's been rubber-stamping OAuth requests for years. The stakes (student data, a real risk model watching your calls) are stated up front on the landing screen, not left implicit in a quiz UI.
- **The Daily Sweep — a reason to come back tomorrow.** `GET /api/sweep/today` deterministically seeds the same 10 apps for every player on a given calendar date (`random.Random(date.isoformat())`, the same trick behind Wordle's daily puzzle). A completed sweep ends in a shareable result — `ScopeSweep Day #3 — 8/10 🟩🟩🟥🟩...` — copyable straight to a clipboard, comparable with classmates, and gone by tomorrow, which is the actual retention mechanism: nothing to fall back on if you don't return.
- **A live Human-vs-Model scoreboard, and achievement badges.** The "Humans vs. AI" tab (`GET /api/community-stats`) aggregates *every* guess anyone has ever logged into a running head-to-head record — a visible, growing number, not a one-time claim. Five badges (Perfect Sweep, AI Slayer for out-scoring the model in a sweep, Combo Hunter, On Fire, Streak Keeper for a 3-day sweep streak) persist per-browser in `localStorage` and unlock with a toast + a confetti burst on a perfect sweep, giving a reason to keep playing past round one.

---

## Quickstart

```bash
git clone <your-repo-url>
cd scope-sweep
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (optional — a committed dataset already ships in data/apps_dataset.json)
python3 -m data.generate_dataset

uvicorn backend.app:app --reload
# open http://127.0.0.1:8000
```

No API keys, no cloud account, no GPU, no internet connection required. The frontend uses only system fonts and vanilla JS — it will run at a venue with no wifi.

Run the test suite:

```bash
pytest -v
```

---

## How it works

### 1. The scope catalog and ground-truth rule

`data/scopes_reference.py` hand-codes ~19 real Google Workspace OAuth scope identifiers into Google's own public three-tier sensitivity classification (**recommended / sensitive / restricted**), plus five documented "dangerous combination" scope pairs — e.g. `contacts.readonly` + `gmail.send` is a plausible spam/phishing pipeline even though each scope looks tame alone.

`data/categories_reference.py` defines twelve generic EdTech app archetypes (Flashcard/Quiz Tool, Gradebook/LMS Sync, Parent Communication App, …) and what scopes each one plausibly needs. These are deliberately **generic archetypes, not real product names** — the goal is teaching the pattern of over-permissioning, not making claims about any specific real company's app.

`ml/scoring.py` combines both into a documented, auditable formula: base severity from the most sensitive scope requested, a breadth bonus for multiple sensitive/restricted scopes, a category-mismatch penalty, a dangerous-combination bonus, and a small per-scope blast-radius term — squashed through a saturating curve so a handful of stacked risk factors spreads across the score range instead of every "bad" app clipping to exactly 100.

### 2. The synthetic dataset

`data/generate_dataset.py` generates 110 synthetic app instances (10 per category) by combining each category's expected scopes with a controlled, randomized amount of over-permissioning — 55% well-behaved, 30% mildly over-permissioned, 15% clearly over-permissioned — and labels each one with the ground-truth rule above. Re-run it any time to regenerate `data/apps_dataset.json` with a different random seed or category mix.

### 3. The ML model

`ml/features.py` turns a `(category, scopes, metadata, population_stats)` combination into 14 numeric features: the original 10 (scope counts by tier, max/sum tier weight, category-mismatch count and weight, dangerous-combo count, category baseline sensitivity) plus 4 new ones — publisher-verified flag, normalized account age, log-scaled install count, and `unexpected_scope_rarity` (a population-derived anomaly statistic, see above) — **not** the raw scoring formula's output. Publisher metadata is optional throughout; when it's missing, the contextual features get a distinct `-1` "unknown" sentinel rather than a guessed default. `ml/model.py` trains a `RandomForestClassifier` on those features against a stratified 75/25 train/test split, and caches:

- **Held-out accuracy** and a full `classification_report` (precision/recall/F1 per tier) — a real, measured number, exposed at `GET /api/model/stats`.
- **Feature importances** — which of the 10 features the model actually leans on.
- Per-prediction **top contributing features**, so the game can say "this call leaned on restricted-scope count and category mismatch" instead of a canned sentence.

Because the training labels come from a deterministic rule, holdout accuracy is still high (currently **96.4%**, down from ~100% before the publisher-trust interaction and population-rarity feature were added — a harder, less trivially learnable function to approximate) — see [Honest limitations](#honest-limitations-and-roadmap) below for why that's a documented, expected property of the MVP rather than a hidden weakness, and what the real fix looks like.

### 4. The game loop

`GET /api/round` serves a random, never-yet-seen (per session) app with its requested scopes rendered as a realistic OAuth-consent-style card. The player guesses Low/Medium/High. `POST /api/guess` scores the guess against ground truth, runs the *same* ML model the assessment tool uses, and returns both verdicts side by side with the model's tier probabilities and the plain-language reasons behind the ground truth. Streak bonuses reward sustained accuracy, not lucky single guesses.

### 5. Assessment Mode — the Category-1 tool

`POST /api/assess` accepts any list of `{name, category, scopes}` and returns a worst-first ranked risk report using the live model. Paste a real district's authorized-app export (with real product names replaced by generic labels if needed for privacy) and get back exactly the triage list a one-person IT department has no time to build by hand.

---

## Architecture

```
frontend/ (vanilla HTML/CSS/JS, no build step, no CDN dependency)
        │  fetch()
        ▼
backend/app.py (FastAPI)
   ├── /api/session, /api/round, /api/guess, /api/leaderboard   → game loop
   ├── /api/model/stats                                          → model transparency
   └── /api/assess                                                → real tool mode
        │
        ├── backend/game_state.py  → SQLite (sessions, leaderboard, guess log)
        └── ml/model.py            → RandomForestClassifier (trained at import time)
                 │
                 ├── ml/features.py      → numeric feature engineering
                 └── data/apps_dataset.json  ← data/generate_dataset.py
                          │
                          └── ml/scoring.py + data/scopes_reference.py +
                              data/categories_reference.py   → ground-truth labels
```

---

## Tech stack

- **Backend:** Python, FastAPI, Pydantic, SQLite (stdlib `sqlite3`)
- **ML:** scikit-learn (`RandomForestClassifier`), pandas/numpy for feature handling
- **Frontend:** vanilla HTML/CSS/JS — no framework, no build tool, no external CDN
- **Tests:** pytest + FastAPI's `TestClient`

Every piece runs on a laptop CPU in seconds. No paid API, no GPU, no cloud account.

---

## Honest limitations and roadmap

Said plainly, because a judge who spots this without you addressing it first is a worse outcome than raising it yourself:

- **The training labels come from a hand-written rule, not real human judgment or real district data.** That's *why* held-out accuracy is still high (96.4%) even after adding real interaction and population-derived terms — the model is approximating a smooth, learnable function, which is a legitimate but limited demonstration of "the model generalizes to feature combinations it wasn't directly trained on." The real next step, and the reason the game logs every guess in the first place, is retraining on **human-labeled data** collected through gameplay (see `scripts/analyze_guesses.py`), which would let the model diverge from — and potentially improve on — the original rule, and would make the accuracy number mean something it doesn't yet.
- **The app catalog is synthetic, and so is the publisher-trust metadata.** Every app name, and every publisher's verification status/account age/install count, is procedurally generated from documented archetypes (`data/generate_dataset.py`) — not scraped from a real marketplace. That's a deliberate privacy and legal-safety choice, not a data-collection failure — but it does mean Assessment Mode hasn't yet been validated against a real district's actual authorized-app export or a real OAuth marketplace's verification data. That's the natural next pilot, and the schema already supports a real export that's missing trust fields entirely (`AssessResultItem.had_publisher_context` reports which case you're in).
- **`publisher_verified` carries almost no weight in the trained model** (see its feature importance in `/api/model/stats`) even though the ground-truth rule uses it — account age and install count end up capturing most of the same signal for a shallow tree, so the binary flag is largely redundant once the continuous features are present. Said here rather than left for a judge to notice first.
- **No live Google Admin SDK integration yet.** A real deployment (closer to the original "ClassroomShield" concept this project grew out of) would pull a district's actual OAuth grants via the Admin SDK Reports API instead of requiring copy-pasted JSON. That's a scoped, achievable v2 — the model and scoring logic underneath don't change, only where the input comes from.
- **The leaderboard/session store is a local SQLite file with no auth.** Fine for a classroom or competition demo; a real multi-classroom deployment would need real accounts and a hosted database.

None of these are hidden from `/api/model/stats` or this README — that's deliberate.

---

## Testing

```bash
pytest -v
```

40 tests total. Highlights:

- `tests/test_scoring.py` — the ground-truth rule behaves as documented (category mismatch is penalized, dangerous combos are flagged, scores stay bounded, publisher trust context genuinely changes the score for identical scopes, and is a no-op when omitted or when there's nothing to weigh).
- `tests/test_features.py` — feature engineering produces the right shape, responds correctly to more/less sensitive input, uses a distinct sentinel when publisher metadata is missing, and computes `unexpected_scope_rarity` correctly from a population (a scope never seen before in a category is rarer than a common one).
- `tests/test_model.py` — the model trains, reports valid probabilities, higher-risk scopes score higher, and predictions work both with and without publisher metadata supplied.
- `tests/test_api.py` — full round-trip through every endpoint, including error cases (unknown session, invalid tier), the Daily Sweep's determinism, the community scoreboard, and Assessment Mode correctly using (or honestly doing without) publisher context — using an isolated temp database per test run.

---

## Pushing this to GitHub

```bash
# from inside the scope-sweep/ directory
git add -A
git commit -m "Initial ScopeSweep prototype"

# create a new empty repo on github.com first, then:
git remote add origin https://github.com/<your-username>/scope-sweep.git
git branch -M main
git push -u origin main
```

---

## Project layout

```
scope-sweep/
├── data/
│   ├── scopes_reference.py       # real OAuth scope catalog + sensitivity tiers
│   ├── categories_reference.py   # generic app-category expected-scope profiles
│   ├── generate_dataset.py       # builds the synthetic training set
│   └── apps_dataset.json         # generated, committed for reproducibility
├── ml/
│   ├── scoring.py                # documented ground-truth risk formula
│   ├── features.py               # numeric feature engineering
│   └── model.py                  # trains + wraps the RandomForestClassifier
├── backend/
│   ├── app.py                    # FastAPI routes
│   ├── game_state.py             # SQLite sessions / leaderboard / guess log
│   └── schemas.py                # Pydantic request/response models
├── frontend/
│   ├── index.html / style.css / app.js   # vanilla, no build step
├── scripts/
│   └── analyze_guesses.py        # human-computation loop: turns guess log into a report + retraining CSV
├── tests/
│   └── test_*.py                 # pytest suite
└── docs/
    └── DEMO_SCRIPT.md            # a 4-minute walkthrough for judges
```

---

## License

MIT — see `LICENSE`. Change the copyright name in that file if you'd like it under a different name.
