// ScopeSweep frontend — vanilla JS, no framework, no build step. Talks to
// the FastAPI backend at the same origin.

const API = "/api";
let sessionId = null;
let currentRound = null;
let roundCount = 0;

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
  });
});

// ---------- Game: start ----------
document.getElementById("startBtn").addEventListener("click", startGame);
document.getElementById("playerNameInput").addEventListener("keydown", e => {
  if (e.key === "Enter") startGame();
});

async function startGame() {
  const name = document.getElementById("playerNameInput").value || "Anonymous";
  const res = await fetch(`${API}/session`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: name }),
  });
  const data = await res.json();
  sessionId = data.session_id;
  roundCount = 0;
  document.getElementById("onboard").classList.add("hidden");
  document.getElementById("gameArea").classList.remove("hidden");
  await loadRound();
}

// ---------- Game: round ----------
async function loadRound() {
  document.getElementById("resultPanel").classList.add("hidden");
  document.getElementById("nextRow").classList.add("hidden");
  document.getElementById("guessRow").querySelectorAll("button").forEach(b => b.disabled = false);

  const res = await fetch(`${API}/round?session_id=${sessionId}`);
  currentRound = await res.json();
  roundCount += 1;

  document.getElementById("appName").textContent = currentRound.name;
  document.getElementById("appCategory").textContent = currentRound.category;
  document.getElementById("appIcon").textContent = currentRound.name[0];
  document.getElementById("hudRound").textContent = roundCount;

  const list = document.getElementById("scopeList");
  list.innerHTML = "";
  currentRound.scopes.forEach(s => {
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

document.querySelectorAll(".guess-btn").forEach(btn => {
  btn.addEventListener("click", () => submitGuess(btn.dataset.tier));
});

async function submitGuess(tier) {
  document.getElementById("guessRow").querySelectorAll("button").forEach(b => b.disabled = true);

  const res = await fetch(`${API}/guess`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, app_id: currentRound.app_id, guess_tier: tier }),
  });
  const r = await res.json();
  renderResult(tier, r);
  updateHud(r.session);
}

function updateHud(session) {
  document.getElementById("hudScore").textContent = session.score;
  document.getElementById("hudStreak").textContent = session.streak;
  const acc = session.rounds_played
    ? Math.round((session.rounds_correct / session.rounds_played) * 100) + "%"
    : "—";
  document.getElementById("hudAccuracy").textContent = acc;
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
  document.getElementById("nextRow").classList.remove("hidden");
}

document.getElementById("nextBtn").addEventListener("click", loadRound);

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
