# ScopeSweep — 4-minute judge demo script

Run `uvicorn backend.app:app` before you're called up, and have
`http://127.0.0.1:8000` already open. Everything below runs fully offline.

## 1. The hook (30 seconds)

> "The average school district has hundreds of EdTech apps with a green
> checkmark on a teacher's Google account, and most of those checkmarks
> got clicked on a Tuesday afternoon during lesson prep — not by anyone
> thinking about what the app can actually see. ScopeSweep is a game that
> teaches people to read an OAuth consent screen like a security analyst
> would, and it's backed by a real machine learning model, not a script
> that just repeats a hardcoded answer."

## 2. Play two rounds live (60 seconds)

- Enter a name, click **Start playing**.
- Round 1: pick an obviously-safe-looking app (few, low-tier scopes).
  Guess **Low**. Show the reveal: ground truth, model's call, probability
  bars, and the plain-language reasons.
- Round 2: pick a round where the app requests a scope combination that
  trips a dangerous-combo flag (or just keep clicking Next until one comes
  up — roughly 1 in 9 apps trips one). Point at the combo warning box:
  *"individually these two scopes look tame — together they're a spam
  pipeline."*

## 3. Prove the AI is real (60 seconds)

- Click the **Model stats** tab.
- Point at held-out accuracy and say it plainly: *"this is a held-out test
  score, not a number I picked — the model never saw these examples during
  training."*
- Point at the feature importance bars: *"the model leans hardest on the
  most-sensitive-scope-requested and the total sensitivity weight — which
  is exactly what a security reviewer would look at first, except this
  model learned that ranking from data instead of me hand-coding it."*

## 4. Show it's also a real tool (60 seconds)

- Click **Assessment mode** → **Load sample district export** → **Run
  assessment**.
- *"This is the exact same model, pointed at a plain list of apps and
  scopes instead of one game round at a time. A school's one IT person
  could paste their district's actual authorized-app list in here and get
  a ranked triage list back in under a second — which is the real tool
  this game is secretly also building."*

## 5. Close on the honest, ambitious part (30 seconds)

> "Every guess anyone makes in this game gets logged — the ground truth,
> the model's call, and the human's call, all three. That log is the raw
> material for retraining this model on real human judgment instead of the
> hand-written rule it started from — that's `scripts/analyze_guesses.py`
> in the repo. That's the actual reason we gamified this instead of just
> shipping a scanner: the game *is* the data collection strategy."

## Anticipated judge questions

- **"Isn't the model just learning your rule back?"** — Yes, and we say so
  in the README. It's trained on engineered features, never on the rule's
  own output, so held-out accuracy demonstrates real generalization to
  unseen feature combinations — but we're upfront that the next real step
  is retraining on human-labeled data from gameplay, not pretending this
  is finished.
- **"Is any of this real user or student data?"** — No. Every app is
  synthetic and procedurally generated. The scope catalog and sensitivity
  tiers are Google's real public documentation; the apps that request them
  are not real products.
- **"How would this actually get used by a school?"** — Assessment Mode is
  the deployment path: point it at a real Admin SDK export (a scoped v2
  feature, not yet built) instead of pasted JSON, and it's the same
  ranked-report workflow, live.
