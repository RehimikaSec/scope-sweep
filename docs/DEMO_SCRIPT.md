# ScopeSweep — 4-minute judge demo script

Run `uvicorn backend.app:app` before you're called up, and have
`http://127.0.0.1:8000` already open on the landing screen. Everything below
runs fully offline. If you've already played today's sweep in rehearsal,
either play it again for the demo (fine — the model's calls don't change)
or lean on Practice Mode for the live rounds and describe the Sweep instead.

## 1. The hook (30 seconds)

Point at the landing screen before clicking anything.

> "You're the newest — and only — app reviewer for a school district of
> 4,200 students. Your predecessor rubber-stamped every OAuth request that
> landed on their desk, and some of those apps can now read or send email
> as any student. Today's queue has 10 requests. A trained risk model has
> already made its own call on each one — I don't get to see it until
> after I commit to mine."

## 2. Play the Daily Sweep live (75 seconds)

- Click **Start today's sweep**. Point at the progress bar and the "vs.
  Model" counter in the HUD before guessing.
- Round 1: pick an app with few, low-tier scopes. Guess **Low**. Show the
  reveal — ground truth, model's call, probability bars, plain-language
  reasons.
- Keep clicking through a few more rounds until one trips a dangerous-combo
  warning (roughly 1 in 9 apps). Point at it: *"individually these two
  scopes look tame — together they're a spam or impersonation pipeline,
  and the model still weighs that correctly."*
- Also point at the publisher badge on the consent card the first time it
  comes up: *"this isn't just 'what scope did it ask for' — verified
  status, account age, and install count are real signals a school IT
  reviewer would actually check, and they change the call."*
- Finish the sweep (or skip ahead if time is short — judges respond well
  to seeing the **recap screen** regardless of the exact score). If you
  land a perfect 10/10, the confetti and badge unlock happen live — let it
  play out, it's a genuine payoff moment, not a scripted animation.

## 3. Point at why this isn't a one-play game (45 seconds)

On the recap screen:

> "This result — Day #3, 8 out of 10 — is copyable and shareable, the same
> mechanic Wordle uses. Everyone who plays today gets the exact same 10
> apps, seeded from today's date server-side, so scores are actually
> comparable. Tomorrow it's a new queue. That's not decoration — it's the
> actual reason someone opens this app twice."

Click into the **Humans vs. AI** tab.

> "Every guess anyone has ever made across every session gets tallied here
> — live. This is the actual data pipeline this whole project is built
> around: gamification isn't just a teaching device, it's how we'd collect
> real human-labeled judgments to eventually retrain the model past the
> hand-written rule it started from."

## 4. Prove the AI is real (45 seconds)

- Click **Model stats**.
- Point at held-out accuracy plainly: *"this is a held-out test score, not
  a number I picked — the model never saw these examples during
  training. It used to sit near 100% before I added real publisher-trust
  and population-anomaly features — 96% now, because the function it's
  approximating actually got harder."*
- Point at feature importance: *"the model leans hardest on the most-
  sensitive-scope-requested and total sensitivity weight — exactly what a
  security reviewer would check first, except this model learned that
  ranking from data instead of me hand-coding it. It's also using account
  age and install count, further down the list — real-world context a
  static per-scope table has no field for at all."*
- If a judge pushes on "isn't this just your rule memorized back": open
  Assessment Mode and run the sample data — `QuickQuiz Pro` and
  `StudyBuddy Beta` request the *identical* six scopes and land at
  different risk levels, purely from publisher trust context. *"A lookup
  table maps a scope list to a score. This maps a scope list **and who's
  asking** to a score — there's no static table that does that."*

## 5. Show it's also a real tool (30 seconds)

- Click **Assessment mode** → **Load sample district export** → **Run
  assessment**.
- *"Same model, pointed at a plain list of apps and scopes instead of one
  game round at a time. A school's one IT person could paste their
  district's actual authorized-app list in here and get a ranked triage
  list back in under a second."*

## 6. Close (15 seconds)

> "Three things had to be true for this to be worth building: the AI had
> to be real and auditable, the game had to give people an actual reason
> to come back, and the same system had to double as something a real
> understaffed IT department could use today. All three are true, and
> you've just watched all three."

## Anticipated judge questions

- **"Isn't this just a lookup table with extra steps — same scope, same
  score, every time?"** — No, and this is worth demonstrating live if
  asked: the ground-truth rule scales scope severity by real publisher
  trust context (verified status, account age, install count), so the
  identical scope list scores differently depending on who's asking — see
  `ml/scoring.py::_trust_context` and `tests/test_scoring.py`. One feature
  (`unexpected_scope_rarity`) is a population-level statistic computed
  across the whole training corpus, not something any single-app rule
  could contain at all. Both are things a static per-scope table has no
  field for, structurally, not just in this implementation.
- **"Isn't the model just learning your rule back?"** — Yes, and the
  README says so directly. It's trained on engineered features, never on
  the rule's own output, so held-out accuracy demonstrates real
  generalization to unseen feature combinations — but we're upfront that
  the next real step is retraining on human-labeled data from gameplay
  (the Humans vs. AI log), not pretending this is finished.
- **"Is the Daily Sweep actually the same for everyone, or does it look
  that way?"** — It's deterministic from the calendar date server-side
  (`random.Random(date.isoformat())`), and `tests/test_api.py` has a test
  asserting two separate calls on the same day return identical rounds in
  identical order — that's not a client-side illusion.
- **"Is any of this real user or student data?"** — No. Every app is
  synthetic and procedurally generated. The scope catalog and sensitivity
  tiers are Google's real public documentation; the apps requesting them
  are not real products.
- **"How would this actually get used by a school?"** — Assessment Mode is
  the deployment path: point it at a real Admin SDK export (a scoped v2
  feature, not yet built) instead of pasted JSON, and it's the same
  ranked-report workflow, live.
