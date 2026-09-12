# ScopeSweep

A game that teaches OAuth-permission literacy by having players guess an app's risk level, then compare their call against a real trained machine learning model — and the same model doubles as a scope-risk auditing tool a school's IT coordinator could run against a real list of authorized apps.

| Category | How ScopeSweep fits |
|---|---|
| **AI-enabled solution** | A `RandomForestClassifier`, trained on 14 engineered features, predicts an app's OAuth risk tier, with a real held-out accuracy score, real feature importances, and a plain-language explanation behind every prediction. |
| **Cybersecurity education** | The game loop is a scored, explained quiz: guess an app's risk tier before the model reveals its own call, then see why both of you landed where you did. |
| **Community-oriented tool** | Assessment Mode runs the same model against a pasted list of apps and scopes and returns a ranked risk report — the workflow a K-12 IT coordinator could run against a district's actual authorized-app export. |

---

## Why this is a real problem, not a hypothetical one

Third-party apps requesting broad OAuth access to a Google account — and getting rubber-stamped — is a documented, ongoing attack surface, not an invented premise:

- **The 2017 "Google Docs" OAuth worm.** A fake app impersonated Google Docs, got users to grant it OAuth access to Gmail and contacts, then auto-emailed everyone in each victim's contact list — spreading to roughly a million Gmail accounts in hours. That's the exact `contacts.readonly` + `gmail.send` dangerous-combination pattern this project's scoring rule flags. ([BankInfoSecurity](https://www.bankinfosecurity.com/attackers-unleash-oauth-worm-via-google-docs-app-a-9888), [CNBC](https://www.cnbc.com/2017/05/04/gmail-google-hack-phishing-attack.html), [Auth0](https://auth0.com/blog/all-you-need-to-know-about-the-google-docs-phishing-attack/))
- **Google itself has changed policy specifically for schools.** Google Workspace for Education now requires domain admins to explicitly review and approve third-party OAuth apps' scope requests, instead of allowing them through by default — a direct response to this exact risk in exactly this sector. ([Google Workspace Updates](https://workspaceupdates.googleblog.com/2023/08/third-party-app-access-enhancements-for-google-workspace-edu.html), [National Law Review](https://natlawreview.com/article/changes-google-workspace-education-terms-service-prompts-audits-third-party))
- **There's a real commercial market built around this exact gap.** Vendors like ManagedMethods sell products specifically to monitor risky OAuth grants inside K-12 Google Workspace domains — because districts kept getting caught out by the rubber-stamping behavior this project's premise describes. ([ManagedMethods](https://managedmethods.com/blog/oauth-risks-and-solutions-for-k-12/))
- **It's an active, current threat, not a stale 2017 story.** OAuth consent phishing targeting schools is still being reported in 2026, and industry research this year describes OAuth-based risk as growing, partly driven by a new wave of AI tools requesting broad account access. ([Security Boulevard](https://securityboulevard.com/2026/07/modern-google-oauth-phishing-what-k-12-schools-need-to-know/), [Material Security study](https://finance.yahoo.com/technology/ai/articles/material-security-study-reveals-oauth-120000050.html))

The apps in this project are synthetic (see [Limitations](#limitations-and-roadmap)), but the problem they model — a school district accumulating unreviewed, over-permissioned third-party OAuth grants — is real and documented.

---

## How it works

### 1. The scope catalog and ground-truth rule

`data/scopes_reference.py` classifies about 19 real Google Workspace OAuth scopes into Google's own public three-tier sensitivity system (**recommended / sensitive / restricted**), plus five documented "dangerous combination" scope pairs — e.g. `contacts.readonly` + `gmail.send` is a plausible spam/phishing pipeline even though each scope looks tame alone.

`data/categories_reference.py` defines twelve generic EdTech app archetypes (Flashcard/Quiz Tool, Gradebook/LMS Sync, Parent Communication App, …) and the scopes each one plausibly needs. These are generic archetypes, not real product names.

`ml/scoring.py` combines both into a documented, auditable formula: base severity from the most sensitive scope requested, a breadth bonus for multiple sensitive/restricted scopes, a category-mismatch penalty, a dangerous-combination bonus, a small per-scope blast-radius term, and a publisher-trust adjustment (see below) — squashed through a saturating curve so the score spreads across the range instead of clustering at the extremes.

### 2. Publisher trust context

Risk doesn't come only from which scopes are requested — it also depends on who's asking. Each synthetic app also carries publisher metadata: whether the publisher is verified, how old the account is, and how many organizations have installed it. That context scales the scope-derived severity up or down — the same scope list scores differently depending on the publisher behind it, the same way a real reviewer would weigh a request differently from an established, verified vendor versus a three-week-old unverified one.

This metadata is optional throughout the system. When it's missing (e.g. a real district export that doesn't track it), both the scoring rule and the model fall back cleanly to scope-only scoring rather than guessing.

### 3. The synthetic dataset

`data/generate_dataset.py` generates 110 synthetic apps (10 per category) by combining each category's expected scopes with a controlled, randomized amount of over-permissioning, and an independently-drawn publisher-trust archetype (new/established × verified/unverified). Every app is labeled with the ground-truth rule above. Re-run it any time to regenerate `data/apps_dataset.json`.

### 4. The ML model

`ml/features.py` turns an app into 14 numeric features: scope counts and weights by tier, category-mismatch signals, dangerous-combo count, the publisher-trust signals (verified flag, account age, install count), and `unexpected_scope_rarity` — how common a given outlier scope actually is within its category, computed from the frequency of that scope across the whole training population. The model is never fed the scoring rule's own output — only these engineered features.

`ml/model.py` trains a `RandomForestClassifier` on a stratified 75/25 train/test split and reports, honestly:

- **Held-out accuracy** and a full precision/recall/F1 report, exposed at `GET /api/model/stats` — currently 96.4%.
- **Feature importances** — which features the model actually leans on.
- Per-prediction **top contributing features**, so the game can explain a specific call instead of showing a canned sentence.

### 5. The game loop

`GET /api/round` serves a random app with its requested scopes rendered as an OAuth-consent-style card, including the publisher's verification badge, account age, and install count. The player guesses Low/Medium/High. `POST /api/guess` scores the guess against ground truth, runs the same model Assessment Mode uses, and returns both verdicts side by side with tier probabilities and plain-language reasoning. Streak bonuses reward sustained accuracy over lucky single guesses.

Two ways to play: the **Daily Sweep** is a fixed set of 10 apps, deterministically chosen from the calendar date (`random.Random(date.isoformat())`), so every player sees the same 10 rounds on a given day and results are shareable and comparable — the same mechanic behind Wordle's daily puzzle. **Practice Mode** is unlimited rounds with no daily reset. A "Humans vs. AI" tab aggregates every guess anyone has logged into a running head-to-head record, and five achievement badges (tracked per-browser) unlock for things like a perfect sweep or a 3-day play streak.

### 6. Assessment Mode

`POST /api/assess` accepts a list of `{name, category, scopes}` (with optional publisher fields) and returns a worst-first ranked risk report using the live model — the same triage list a one-person IT department would otherwise have to build by hand from a district's authorized-app export.

---

## Architecture

```
frontend/ (vanilla HTML/CSS/JS, no build step, no CDN dependency)
        │  fetch()
        ▼
backend/app.py (FastAPI)
   ├── /api/session, /api/round, /api/guess, /api/leaderboard   → game loop
   ├── /api/sweep/today, /api/community-stats                   → Daily Sweep + scoreboard
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

Every piece runs on a laptop CPU in seconds. No paid API, no GPU, no cloud account required.

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

No API keys, no cloud account, no internet connection required to run it. The frontend uses only system fonts and vanilla JS.

---

## Testing

```bash
pytest -v
```

40 tests across four files:

- `tests/test_scoring.py` — the ground-truth rule behaves as documented: category mismatch is penalized, dangerous combos are flagged, scores stay bounded, and publisher trust context changes the score correctly (and is a no-op when omitted).
- `tests/test_features.py` — feature engineering produces the right shape, responds correctly to more/less sensitive input, and computes the population-derived rarity feature correctly.
- `tests/test_model.py` — the model trains, reports valid probabilities, and predictions work both with and without publisher metadata supplied.
- `tests/test_api.py` — full round-trip through every endpoint, including error cases, the Daily Sweep's determinism, the community scoreboard, and Assessment Mode.

---

## Limitations and roadmap

- **Training labels come from a hand-written rule, not real human judgment or real district data.** The next step is retraining on human-labeled data collected through gameplay (see `scripts/analyze_guesses.py`), which every guess is already logged to support.
- **The app catalog and publisher metadata are synthetic**, generated from documented archetypes rather than scraped from a real marketplace. Assessment Mode hasn't yet been validated against a real district's authorized-app export.
- **No live Google Admin SDK integration yet.** A real deployment would pull a district's actual OAuth grants via the Admin SDK Reports API instead of requiring copy-pasted JSON — the scoring and model underneath wouldn't need to change, only where the input comes from.
- **The leaderboard/session store is a local SQLite file with no auth.** Fine for a demo; a real multi-classroom deployment would need real accounts and a hosted database.

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
│   └── analyze_guesses.py        # turns the guess log into a report + retraining CSV
├── tests/
│   └── test_*.py                 # pytest suite
└── docs/
    └── DEMO_SCRIPT.md            # a walkthrough of the app
```

---

## License

MIT — see `LICENSE`. Change the copyright name in that file if you'd like it under a different name.
