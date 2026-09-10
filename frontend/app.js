// ScopeSweep frontend — vanilla JS, no framework, no build step. Talks to
// the FastAPI backend at the same origin.

const API = "/api";
const LS_KEY = "scopesweep_lifetime_v1";

// ---------- Lifetime, per-browser stats (achievements, day streak) ----------
// Deliberately localStorage, not the server: this is per-player, per-device
// bragging-rights state, not shared game data. Wrapped defensively since a
// private window or locked-down browser can throw on access.
function loadLifetime() {
  const defaults = {
    totalSweepsPlayed: 0, dayStreak: 0, lastSweepDate: null,
    perfectSweeps: 0, aiSlayerCount: 0, comboCatchesLifetime: 0,
    badgesUnlocked: [], everHitStreak5: false,
  };
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? { ...defaults, ...JSON.parse(raw) } : defaults;
  } catch (e) { return defaults; }
}
function saveLifetime(state) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
}
let lifetime = loadLifetime();

const BADGES = {
  perfect:       { emoji: "🎯", label: "Perfect Sweep",  desc: "Get all 10 rounds right in one Daily Sweep." },
  ai_slayer:     { emoji: "🤖", label: "AI Slayer",       desc: "Out-score the model's own accuracy in a sweep." },
  combo_hunter:  { emoji: "🕵️", label: "Combo Hunter",    desc: "Correctly flag 5 dangerous scope combinations." },
  streak5:       { emoji: "🔥", label: "On Fire",         desc: "Hit a 5-guess correct streak." },
  streak_keeper: { emoji: "📅", label: "Streak Keeper",   desc: "Play the Daily Sweep 3 days in a row." },
};

function unlockBadge(id) {
  if (lifetime.badgesUnlocked.includes(id)) return false;
  lifetime.badgesUnlocked.push(id);
  saveLifetime(lifetime);
  const b = BADGES[id];
  showToast(`${b.emoji} Badge unlocked — ${b.label}`);
  return true;
}

function showToast(text) {
  const host = document.getElementById("toastHost");
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = text;
  host.appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

// ---------- Category -> deterministic color, so app icons aren't one flat gray ----------
const ICON_PALETTE = ["#5aa9e6", "#8f7ae6", "#e6a35a", "#5ae6b8", "#e65a8f", "#a3e65a", "#e6c25a", "#5ac9e6"];
function colorForCategory(cat) {
  let h = 0;
  for (let i = 0; i < cat.length; i++) h = (h * 31 + cat.charCodeAt(i)) >>> 0;
  return ICON_PALETTE[h % ICON_PALETTE.length];
}

// ---------- App state ----------
let sessionId = null;
let mode = null;             // "sweep" | "practice"
let sweepRounds = [];        // for sweep mode: the fixed 10 rounds
let sweepIndex = 0;
let sweepDate = null;
let sweepDayNumber = null;
let currentRound = null;
let roundCount = 0;
let humanWins = 0, modelWins = 0, ties = 0;
let sweepCorrectCount = 0, sweepModelCorrectCount = 0;

// ---------- Confetti (lightweight, no library) ----------
function burstConfetti() {
  const canvas = document.getElementById("confettiCanvas");
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const ctx = canvas.getContext("2d");
  const colors = ["#5aa9e6", "#8f7ae6", "#e6c25a", "#4caf7d", "#e2685c"];
  const pieces = Array.from({ length: 140 }, () => ({
    x: Math.random() * canvas.width,
    y: -20 - Math.random() * canvas.height * 0.3,
    r: 3 + Math.random() * 4,
    c: colors[Math.floor(Math.random() * colors.length)],
    vy: 2 + Math.random() * 3,
    vx: -1.5 + Math.random() * 3,
    rot: Math.random() * 360,
    vrot: -6 + Math.random() * 12,
  }));
  let frame = 0;
  function tick() {
    frame++;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach(p => {
      p.x += p.vx; p.y += p.vy; p.rot += p.vrot;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate((p.rot * Math.PI) / 180);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.r, -p.r, p.r * 2, p.r * 2);
      ctx.restore();
    });
    if (frame < 130) requestAnimationFrame(tick);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  tick();
}

// ---------- Tabs ----------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "leaderboard") loadLeaderboard();
    if (btn.dataset.tab === "model") loadModelStats();
    if (btn.dataset.tab === "assess") loadScopeRef();
    if (btn.dataset.tab === "community") loadCommunityStats();
  });
});

// ---------- Landing screen setup ----------
async function initLanding() {
  document.getElementById("streakChip").hidden = lifetime.dayStreak < 1;
  document.getElementById("streakChipVal").textContent = lifetime.dayStreak;
  renderBadgeShelf();
  try {
    const res = await fetch(`${API}/sweep/today`);
    const data = await res.json();
    sweepDayNumber = data.day_number;
    document.getElementById("dayNumberHero").textContent = data.day_number;
    document.getElementById("dayNumberCard").textContent = data.day_number;
  } catch (e) { /* server not reachable yet on first paint — fine */ }
}

function renderBadgeShelf() {
  const host = document.getElementById("badgeShelf");
  host.innerHTML = Object.entries(BADGES).map(([id, b]) => {
    const unlocked = lifetime.badgesUnlocked.includes(id);
    return `<span class="badge-pill ${unlocked ? "unlocked" : ""}" title="${b.desc}">${b.emoji} ${b.label}</span>`;
  }).join("");
}

document.getElementById("startSweepBtn").addEventListener("click", () => startGame("sweep"));
document.getElementById("startPracticeBtn").addEventListener("click", () => startGame("practice"));
[document.getElementById("sweepNameInput"), document.getElementById("practiceNameInput")].forEach(inp => {
  inp.addEventListener("keydown", e => { if (e.key === "Enter") startGame(inp.id.includes("sweep") ? "sweep" : "practice"); });
});

async function startGame(chosenMode) {
  mode = chosenMode;
  const nameInput = mode === "sweep" ? "sweepNameInput" : "practiceNameInput";
  const name = document.getElementById(nameInput).value || "Anonymous";

  const res = await fetch(`${API}/session`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: name }),
  });
  sessionId = (await res.json()).session_id;

  roundCount = 0; humanWins = 0; modelWins = 0; ties = 0;
  sweepCorrectCount = 0; sweepModelCorrectCount = 0;

  document.getElementById("onboard").classList.add("hidden");
  document.getElementById("recapArea").classList.add("hidden");
  document.getElementById("gameArea").classList.remove("hidden");
  document.getElementById("hudStreakTile").classList.remove("shake");

  if (mode === "sweep") {
    const r = await fetch(`${API}/sweep/today`);
    const data = await r.json();
    sweepDate = data.date;
    sweepDayNumber = data.day_number;
    sweepRounds = data.rounds;
    sweepIndex = 0;
    document.getElementById("progressRow").hidden = false;
    loadSweepRound();
  } else {
    document.getElementById("progressRow").hidden = true;
    loadPracticeRound();
  }
  updateVsModelHud();
}

// ---------- Rendering a round (shared by both modes) ----------
function renderRoundCard(roundData) {
  document.getElementById("resultPanel").classList.add("hidden");
  document.getElementById("nextRow").classList.add("hidden");
  document.getElementById("guessRow").querySelectorAll("button").forEach(b => {
    b.disabled = false;
    b.classList.remove("chosen-correct", "chosen-wrong");
  });

  document.getElementById("appName").textContent = roundData.name;
  document.getElementById("appCategory").textContent = roundData.category;
  const icon = document.getElementById("appIcon");
  icon.textContent = roundData.name[0];
  icon.style.background = colorForCategory(roundData.category);

  const list = document.getElementById("scopeList");
  list.innerHTML = "";
  roundData.scopes.forEach(s => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="scope-tier-dot ${s.tier}"></span>
      <div>
        <div class="scope-label">${s.label}</div>
        <div class="scope-desc">${s.desc}</div>
        <div class="scope-id">${s.id}</div>
      </div>`;
    list.appendChild(li);
  });
}

function loadPracticeRound() {
  fetch(`${API}/round?session_id=${sessionId}`).then(r => r.json()).then(data => {
    currentRound = data;
    roundCount += 1;
    document.getElementById("hudRound") && (document.getElementById("hudRound").textContent = roundCount);
    renderRoundCard(data);
  });
}

function loadSweepRound() {
  if (sweepIndex >= sweepRounds.length) { showRecap(); return; }
  currentRound = sweepRounds[sweepIndex];
  const pct = Math.round((sweepIndex / sweepRounds.length) * 100);
  document.getElementById("progressFill").style.width = pct + "%";
  document.getElementById("progressLabel").textContent = `Round ${sweepIndex + 1} / ${sweepRounds.length}`;
  renderRoundCard(currentRound);
}

// ---------- Guessing ----------
document.querySelectorAll(".guess-btn").forEach(btn => {
  btn.addEventListener("click", () => submitGuess(btn.dataset.tier, btn));
});

async function submitGuess(tier, btnEl) {
  document.getElementById("guessRow").querySelectorAll("button").forEach(b => b.disabled = true);

  const payload = {
    session_id: sessionId, app_id: currentRound.app_id, guess_tier: tier, mode,
  };
  if (mode === "sweep") payload.sweep_date = sweepDate;

  const res = await fetch(`${API}/guess`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const r = await res.json();

  btnEl.classList.add(r.is_correct ? "chosen-correct" : "chosen-wrong");
  renderResult(tier, r);
  updateHud(r.session, r.is_correct);

  if (mode === "sweep") {
    if (r.is_correct) sweepCorrectCount++;
    if (r.model_agreed_with_truth) sweepModelCorrectCount++;
  }

  if (r.is_correct && !r.model_agreed_with_truth) humanWins++;
  else if (!r.is_correct && r.model_agreed_with_truth) modelWins++;
  else ties++;
  updateVsModelHud();

  checkImmediateBadges(r);
}

function checkImmediateBadges(r) {
  if (r.session.streak >= 5) unlockBadge("streak5");
  if (r.is_correct && r.ground_truth_tier === "High" && r.tripped_combos.length > 0) {
    lifetime.comboCatchesLifetime += 1;
    saveLifetime(lifetime);
    if (lifetime.comboCatchesLifetime >= 5) unlockBadge("combo_hunter");
  }
}

function updateHud(session, wasCorrect) {
  const scoreEl = document.getElementById("hudScore");
  const streakEl = document.getElementById("hudStreak");
  scoreEl.textContent = session.score;
  streakEl.textContent = session.streak;
  const acc = session.rounds_played
    ? Math.round((session.rounds_correct / session.rounds_played) * 100) + "%"
    : "—";
  document.getElementById("hudAccuracy").textContent = acc;

  scoreEl.classList.remove("pulse"); void scoreEl.offsetWidth; scoreEl.classList.add("pulse");
  const streakTile = document.getElementById("hudStreakTile");
  if (wasCorrect) {
    streakEl.classList.remove("pulse"); void streakEl.offsetWidth; streakEl.classList.add("pulse");
  } else {
    streakTile.classList.remove("shake"); void streakTile.offsetWidth; streakTile.classList.add("shake");
  }
}

function updateVsModelHud() {
  document.getElementById("hudVsModel").textContent = `${humanWins}–${modelWins}`;
}

function renderResult(guessTier, r) {
  const panel = document.getElementById("resultPanel");
  panel.className = "result-panel " + (r.is_correct ? "correct" : "incorrect");

  const probRows = ["Low", "Medium", "High"].map(t => `
    <div class="prob-bar-row">
      <span>${t}</span>
      <div class="prob-bar-track"><div class="prob-bar-fill ${t}" style="width:${Math.round((r.model_probabilities[t] || 0) * 100)}%"></div></div>
      <span>${Math.round((r.model_probabilities[t] || 0) * 100)}%</span>
    </div>`).join("");

  const comboHtml = r.tripped_combos.length
    ? r.tripped_combos.map(c => `<div class="combo-note">⚠ ${c}</div>`).join("")
    : "";

  const modelNote = r.model_agreed_with_truth
    ? "The model called this one correctly too."
    : "The model actually got this one wrong — even trained models miss edge cases, which is exactly why a human reviewer still matters.";

  panel.innerHTML = `
    <div class="result-headline">${r.is_correct ? "✓ Correct" : "✗ Not quite"} — you guessed ${guessTier}, +${r.points_earned} pts</div>
    <div class="result-sub">${modelNote}</div>
    <div class="verdict-row">
      <div class="verdict-block">
        <div class="verdict-label">Ground truth</div>
        <div class="verdict-val tier-${r.ground_truth_tier}">${r.ground_truth_tier} (${r.ground_truth_score}/100)</div>
      </div>
      <div class="verdict-block">
        <div class="verdict-label">Model's call</div>
        <div class="verdict-val tier-${r.model_tier}">${r.model_tier} (${r.model_score}/100)</div>
      </div>
    </div>
    <div class="prob-bars">${probRows}</div>
    <div class="verdict-label" style="margin-bottom:6px;">Why</div>
    <ul class="reason-list">${r.reasons.map(x => `<li>${x}</li>`).join("")}</ul>
    ${comboHtml}
  `;
  panel.classList.remove("hidden");

  const nextRow = document.getElementById("nextRow");
  nextRow.classList.remove("hidden");
  nextRow.innerHTML = mode === "sweep"
    ? `<button id="nextBtn" class="btn-primary">${sweepIndex + 1 >= sweepRounds.length ? "See results →" : "Next app →"}</button>`
    : `<button id="finishPracticeBtn" class="btn-secondary">Finish & see summary</button>
       <button id="nextBtn" class="btn-primary">Next app →</button>`;

  document.getElementById("nextBtn").addEventListener("click", () => {
    if (mode === "sweep") { sweepIndex++; loadSweepRound(); }
    else loadPracticeRound();
  });
  const finishBtn = document.getElementById("finishPracticeBtn");
  if (finishBtn) finishBtn.addEventListener("click", showRecap);
}

// ---------- Recap screen ----------
function resultStrip(results) {
  return results.map(ok => (ok ? "🟩" : "🟥")).join("");
}

async function showRecap() {
  document.getElementById("gameArea").classList.add("hidden");
  document.getElementById("recapArea").classList.remove("hidden");

  const session = await (await fetch(`${API}/session/${sessionId}`)).json();
  const acc = session.rounds_played ? Math.round((session.rounds_correct / session.rounds_played) * 100) : 0;

  let badgesThisRun = [];
  let title = "Session complete";
  let strip = "";

  if (mode === "sweep") {
    const today = sweepDate;
    if (lifetime.lastSweepDate === today) {
      // already played today -- don't double-count the streak
    } else {
      const yesterday = new Date(today + "T00:00:00");
      yesterday.setDate(yesterday.getDate() - 1);
      const yStr = yesterday.toISOString().slice(0, 10);
      lifetime.dayStreak = (lifetime.lastSweepDate === yStr) ? lifetime.dayStreak + 1 : 1;
      lifetime.lastSweepDate = today;
      lifetime.totalSweepsPlayed += 1;
    }

    if (sweepCorrectCount === sweepRounds.length) { lifetime.perfectSweeps += 1; if (unlockBadge("perfect")) badgesThisRun.push("perfect"); burstConfetti(); }
    if (sweepCorrectCount > sweepModelCorrectCount) { lifetime.aiSlayerCount += 1; if (unlockBadge("ai_slayer")) badgesThisRun.push("ai_slayer"); }
    if (lifetime.dayStreak >= 3) { if (unlockBadge("streak_keeper")) badgesThisRun.push("streak_keeper"); }
    saveLifetime(lifetime);

    title = sweepCorrectCount === sweepRounds.length ? "Perfect sweep! 🎯"
          : sweepCorrectCount >= sweepRounds.length * 0.7 ? "Nice work"
          : "Tough queue today";
    strip = `ScopeSweep Day #${sweepDayNumber} — ${sweepCorrectCount}/${sweepRounds.length}\n` +
            `Beat the AI: ${sweepCorrectCount > sweepModelCorrectCount ? "yes 🤖💥" : sweepCorrectCount === sweepModelCorrectCount ? "tied" : "not today"}`;
  }

  const vsLine = `${humanWins}–${modelWins}${ties ? ` (${ties} tied)` : ""}`;

  const card = document.getElementById("recapCard");
  card.innerHTML = `
    <div class="recap-title">${title}</div>
    <div class="recap-sub">${mode === "sweep" ? `Day #${sweepDayNumber} · ${session.player_name}` : `Practice session · ${session.player_name}`}</div>
    <div class="recap-stats">
      <div class="stat-tile"><div class="stat-label">Score</div><div class="stat-val">${session.score}</div></div>
      <div class="stat-tile"><div class="stat-label">Accuracy</div><div class="stat-val">${acc}%</div></div>
      <div class="stat-tile"><div class="stat-label">Best streak</div><div class="stat-val">${session.best_streak}</div></div>
      <div class="stat-tile"><div class="stat-label">vs. Model</div><div class="stat-val">${vsLine}</div></div>
    </div>
    ${mode === "sweep" ? `<div class="recap-strip">${resultStrip(Array.from({length: sweepRounds.length}, (_, i) => i < sweepCorrectCount))}</div>` : ""}
    ${badgesThisRun.length ? `<div class="recap-badges">${badgesThisRun.map(id => `<span class="badge-pill unlocked">${BADGES[id].emoji} ${BADGES[id].label}</span>`).join("")}</div>` : ""}
    <div class="recap-actions">
      ${mode === "sweep" ? `<button id="copyResultBtn" class="btn-secondary">Copy shareable result</button>` : ""}
      <button id="recapPracticeBtn" class="btn-secondary">Practice mode</button>
      <button id="recapHomeBtn" class="btn-primary">Back to home</button>
    </div>
    <p class="lede small">${mode === "sweep" ? "Come back tomorrow for a new sweep." : "Head to the Humans vs. AI tab to see how your guesses stack up community-wide."}</p>
  `;

  const copyBtn = document.getElementById("copyResultBtn");
  if (copyBtn) copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(strip);
      copyBtn.textContent = "Copied!";
      setTimeout(() => { copyBtn.textContent = "Copy shareable result"; }, 1800);
    } catch (e) {
      copyBtn.textContent = "Couldn't copy — select manually";
    }
  });
  document.getElementById("recapPracticeBtn").addEventListener("click", () => startGame("practice"));
  document.getElementById("recapHomeBtn").addEventListener("click", () => {
    document.getElementById("recapArea").classList.add("hidden");
    document.getElementById("onboard").classList.remove("hidden");
    initLanding();
  });
}

// ---------- Leaderboard ----------
async function loadLeaderboard() {
  const res = await fetch(`${API}/leaderboard`);
  const data = await res.json();
  const tbody = document.querySelector("#lbTable tbody");
  tbody.innerHTML = "";
  data.entries.forEach((e, i) => {
    const acc = e.rounds_played ? Math.round((e.rounds_correct / e.rounds_played) * 100) + "%" : "—";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i + 1}</td><td>${escapeHtml(e.player_name)}</td><td>${e.score}</td><td>${e.best_streak}</td><td>${acc}</td><td>${e.rounds_played}</td>`;
    tbody.appendChild(tr);
  });
  if (data.entries.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:var(--ink-faint)">No sessions played yet.</td></tr>`;
  }
}

// ---------- Humans vs AI (community stats) ----------
async function loadCommunityStats() {
  const res = await fetch(`${API}/community-stats`);
  const d = await res.json();
  const host = document.getElementById("communityStatsHost");

  if (!d.total_guesses) {
    host.innerHTML = `<p class="lede">No guesses logged yet — play a round to start the scoreboard.</p>`;
    return;
  }

  const humanPct = Math.round(d.human_accuracy * 100);
  const modelPct = Math.round(d.model_accuracy * 100);
  const total = d.human_wins + d.model_wins + d.ties;
  const hw = total ? (d.human_wins / total) * 100 : 0;
  const mw = total ? (d.model_wins / total) * 100 : 0;
  const tw = total ? (d.ties / total) * 100 : 0;

  const disputedHtml = d.most_disputed_apps.length
    ? d.most_disputed_apps.map(a => `<div class="disputed-row"><span>${escapeHtml(a.category)}</span><span class="mono">${a.n_guesses} guesses, ${a.n_distinct_guesses} different answers</span></div>`).join("")
    : `<p class="lede small">Not enough overlapping guesses yet to find a disputed app.</p>`;

  host.innerHTML = `
    <div class="vs-hero">
      <div class="vs-side human"><div class="vs-label">Humans</div><div class="vs-pct">${humanPct}%</div><div class="lede small">accuracy across ${d.total_guesses} guesses</div></div>
      <div class="vs-divider">VS</div>
      <div class="vs-side model"><div class="vs-label">Model</div><div class="vs-pct">${modelPct}%</div><div class="lede small">accuracy on the same rounds</div></div>
    </div>
    <h3 class="sub-head">Head-to-head, round by round</h3>
    <p class="lede small">Who got it right when the other didn't.</p>
    <div class="vs-bar">
      <div class="vs-bar-human" style="width:${hw}%"></div>
      <div class="vs-bar-tie" style="width:${tw}%"></div>
      <div class="vs-bar-model" style="width:${mw}%"></div>
    </div>
    <p class="lede small">Humans won ${d.human_wins} · Model won ${d.model_wins} · Tied ${d.ties}</p>
    <h3 class="sub-head">Most-disputed apps</h3>
    <p class="lede small">Where players' guesses disagree with each other most — the exact signal <code>scripts/analyze_guesses.py</code> is built to surface.</p>
    <div class="disputed-list">${disputedHtml}</div>
  `;
}

// ---------- Model stats ----------
async function loadModelStats() {
  const res = await fetch(`${API}/model/stats`);
  const data = await res.json();

  const grid = document.getElementById("modelStatsGrid");
  grid.innerHTML = `
    <div class="stat-tile"><div class="stat-label">Held-out accuracy</div><div class="stat-val">${Math.round(data.holdout_accuracy * 100)}%</div></div>
    <div class="stat-tile"><div class="stat-label">Training examples</div><div class="stat-val">${data.n_train}</div></div>
    <div class="stat-tile"><div class="stat-label">Test examples</div><div class="stat-val">${data.n_test}</div></div>
    <div class="stat-tile"><div class="stat-label">Total apps</div><div class="stat-val">${data.n_apps_total}</div></div>
  `;

  const maxImp = Math.max(...data.feature_importances.map(f => f.importance));
  const bars = document.getElementById("featureBars");
  bars.innerHTML = data.feature_importances.map(f => `
    <div class="fbar-row">
      <span class="mono">${f.feature}</span>
      <div class="fbar-track"><div class="fbar-fill" style="width:${(f.importance / maxImp) * 100}%"></div></div>
      <span class="mono">${(f.importance * 100).toFixed(1)}%</span>
    </div>`).join("");
}

// ---------- Assessment mode ----------
const SAMPLE_ASSESS = [
  { name: "QuickQuiz Pro", category: "Flashcard / Quiz Tool",
    scopes: ["openid", "userinfo.email", "userinfo.profile", "drive.file", "contacts.readonly", "gmail.send"] },
  { name: "ClassBoard Live", category: "Digital Whiteboard",
    scopes: ["openid", "userinfo.email", "userinfo.profile", "drive.file"] },
  { name: "RosterSync", category: "Attendance Tracker",
    scopes: ["openid", "userinfo.email", "classroom.rosters.readonly", "classroom.courses.readonly", "drive"] },
  { name: "ParentPing", category: "Parent Communication App",
    scopes: ["openid", "userinfo.email", "userinfo.profile", "gmail.send", "contacts.readonly"] },
  { name: "FormFlow", category: "Survey / Forms Tool",
    scopes: ["openid", "userinfo.email", "forms.body", "gmail.readonly", "admin.directory.user.readonly"] },
];

document.getElementById("loadSampleBtn").addEventListener("click", () => {
  document.getElementById("assessInput").value = JSON.stringify(SAMPLE_ASSESS, null, 2);
});

document.getElementById("runAssessBtn").addEventListener("click", async () => {
  const raw = document.getElementById("assessInput").value.trim();
  const resultsDiv = document.getElementById("assessResults");
  let apps;
  try {
    apps = JSON.parse(raw || "[]");
  } catch (e) {
    resultsDiv.innerHTML = `<p style="color:var(--high)">Couldn't parse that as JSON: ${e.message}</p>`;
    return;
  }
  const res = await fetch(`${API}/assess`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ apps }),
  });
  const data = await res.json();
  renderAssessResults(data.results);
});

function renderAssessResults(results) {
  const div = document.getElementById("assessResults");
  if (!results.length) { div.innerHTML = ""; return; }
  const rows = results.map(r => `
    <tr>
      <td><strong>${escapeHtml(r.name)}</strong><div class="assess-reason">${escapeHtml(r.category)}</div></td>
      <td><span class="tier-pill ${r.model_tier}">${r.model_tier}</span></td>
      <td class="mono">${r.model_score}</td>
      <td>${r.reasons.map(x => `<div class="assess-reason">• ${escapeHtml(x)}</div>`).join("")}
          ${r.unrecognized_scopes.length ? `<div class="assess-reason">Unrecognized: ${r.unrecognized_scopes.join(", ")}</div>` : ""}</td>
    </tr>`).join("");
  div.innerHTML = `
    <table class="assess-table">
      <thead><tr><th>App</th><th>Risk</th><th>Score</th><th>Why</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function loadScopeRef() {
  const el = document.getElementById("scopeRefList");
  if (el.dataset.loaded) return;
  const res = await fetch(`${API}/scopes`);
  const data = await res.json();
  el.innerHTML = Object.entries(data).map(([id, meta]) =>
    `<div>${id} <span style="color:var(--ink-faint)">(${meta.tier})</span></div>`).join("");
  el.dataset.loaded = "1";
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ---------- Boot ----------
initLanding();
