// =====================================================
// Wissenswerkstatt - Client-Logik (Vanilla JS)
// =====================================================

const state = {
  topics: [],
  selectedTopic: null,
  sessionId: null,
  cards: [],            // fällige Karten
  pendingQuestions: {}, // cardId -> question text
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------- Toast ---------------------------------------
function toast(msg, kind = "") {
  const el = $("#toast");
  el.className = "toast show " + kind;
  el.textContent = msg;
  setTimeout(() => el.classList.remove("show"), 2500);
}

// ---------- API-Helfer ----------------------------------
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

// ---------- Tabs ----------------------------------------
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "review") loadReview();
    if (btn.dataset.tab === "progress") loadProgress();
  });
});

// ---------- Themen laden --------------------------------
async function loadTopics() {
  const topics = await api("/api/topics");
  state.topics = topics;
  const grid = $("#topicGrid");
  grid.innerHTML = "";
  for (const t of topics) {
    const el = document.createElement("div");
    el.className = "topic";
    el.innerHTML = `<div class="t-label">${t.label}</div>
                    <div class="t-desc">${t.description}</div>`;
    el.addEventListener("click", () => {
      $$(".topic").forEach((x) => x.classList.remove("selected"));
      el.classList.add("selected");
      state.selectedTopic = t.id;
    });
    grid.appendChild(el);
  }
}

// ---------- Sitzung starten -----------------------------
$("#startBtn").addEventListener("click", async () => {
  $("#startBtn").disabled = true;
  try {
    const s = await api("/api/session/start", {
      method: "POST",
      body: JSON.stringify({ topic: state.selectedTopic }),
    });
    state.sessionId = s.id;
    $("#sessionSetup").classList.add("hidden");
    $("#sessionActive").classList.remove("hidden");
    $("#sessionTopicLabel").textContent =
      state.selectedTopic ? `· ${state.topics.find(t => t.id === state.selectedTopic)?.label}` : "";
    // Intro aus DB lesen
    const info = await api(`/api/session/${state.sessionId}`);
    addBubble("assistant", info.started_at ? "Sitzung läuft." : "", null);
    // Direkt die erste echte Assistenten-Nachricht vom Backend holen:
    await refreshIntro();
  } catch (e) {
    toast("Fehler: " + e.message, "error");
  } finally {
    $("#startBtn").disabled = false;
  }
});

async function refreshIntro() {
  // Wir holen die ersten Nachrichten via Session-Info.
  // Intro wurde serverseitig gespeichert — wir laden es per History.
  const hist = await api(`/api/session/${state.sessionId}/history`);
  renderHistory(hist);
}

async function renderHistory(messages) {
  const chat = $("#chat");
  chat.innerHTML = "";
  for (const m of messages) {
    addBubble(m.role, m.content, null, false);
  }
  chat.scrollTop = chat.scrollHeight;
}

// ---------- Chat ----------------------------------------
$("#chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#chatInput");
  const text = input.value.trim();
  if (!text || !state.sessionId) return;
  addBubble("user", text, null);
  input.value = "";
  try {
    const r = await api(`/api/session/${state.sessionId}/message`, {
      method: "POST",
      body: JSON.stringify({ message: text }),
    });
    addBubble("assistant", r.reply, r.evaluation);
  } catch (err) {
    toast("Sende-Fehler: " + err.message, "error");
  }
});

function addBubble(role, content, evaluation, scroll = true) {
  const chat = $("#chat");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = content;
  if (evaluation) {
    const e = document.createElement("span");
    e.className = "eval " + evaluation;
    e.textContent = labelEval(evaluation);
    div.appendChild(e);
  }
  chat.appendChild(div);
  if (scroll) chat.scrollTop = chat.scrollHeight;
}

function labelEval(e) {
  return {
    korrekt: "korrekt",
    teilweise: "teilweise korrekt",
    unklar: "unklar",
    falsch: "falsch",
    nicht_beantwortet: "nicht beantwortet",
  }[e] || e;
}

// ---------- Sitzung beenden -----------------------------
$("#endBtn").addEventListener("click", () => {
  $("#sessionActive").classList.add("hidden");
  $("#sessionSummary").classList.remove("hidden");
  $("#merksaetze").innerHTML = "<li class='muted'>Wird geladen …</li>";
  $("#newCards").innerHTML = "";
  // Sofort die LLM-Zusammenfassung anfordern
  requestSummary();
});

async function requestSummary() {
  // Wir nutzen close mit self_rating = -1 als Trigger, ohne ihn zu persistieren
  // (besser: separater endpoint). Hier pragmatisch: erst _draft_ summary holen.
  // Wir machen es so: erst User klickt "Bewertung speichern", dann senden wir beides.
  // Aber wir wollen die LLM-Summary schon VOR der Bewertung sehen.
  // -> Wir rufen /api/session/{id}/preview-summary auf.
  try {
    const draft = await api(`/api/session/${state.sessionId}/preview-summary`, { method: "POST" });
    showSummary(draft.merksaetze, draft.karteikarten, /*locked*/ false);
  } catch (e) {
    // Fallback: zeige leere Felder
    showSummary(["(LLM nicht erreichbar)"], [], false);
  }
}

function showSummary(merksaetze, karten, locked) {
  $("#merksaetze").innerHTML = "";
  for (const m of merksaetze) {
    const li = document.createElement("li");
    li.textContent = m;
    $("#merksaetze").appendChild(li);
  }
  $("#newCards").innerHTML = "";
  if (!karten.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "Keine neuen Karten.";
    $("#newCards").appendChild(li);
  } else {
    for (const k of karten) {
      const li = document.createElement("li");
      li.innerHTML = `<b>${escapeHtml(k.front)}</b> — ${escapeHtml(k.back)} <span class="muted">(${k.topic})</span>`;
      $("#newCards").appendChild(li);
    }
  }
}

$("#confirmEndBtn").addEventListener("click", async () => {
  const r = document.querySelector('input[name="rating"]:checked');
  if (!r) { toast("Bitte Antwortsicherheit bewerten.", "error"); return; }
  try {
    const final = await api(`/api/session/${state.sessionId}/confirm-end`, {
      method: "POST",
      body: JSON.stringify({ self_rating: Number(r.value) }),
    });
    toast("Sitzung gespeichert.", "ok");
    showSummary(final.merksaetze, final.karteikarten, true);
    $("#confirmEndBtn").disabled = true;
    // Nächsten Wiederholungstermin vorschlagen
    suggestNextReview();
    refreshDueBadge();
  } catch (e) {
    toast("Fehler: " + e.message, "error");
  }
});

$("#newSessionBtn").addEventListener("click", () => {
  state.sessionId = null;
  state.selectedTopic = null;
  $$(".topic").forEach((x) => x.classList.remove("selected"));
  $("#sessionSummary").classList.add("hidden");
  $("#sessionActive").classList.add("hidden");
  $("#sessionSetup").classList.remove("hidden");
  $("#confirmEndBtn").disabled = false;
  $("#chat").innerHTML = "";
  document.querySelectorAll('input[name="rating"]').forEach(r => r.checked = false);
});

async function suggestNextReview() {
  try {
    const p = await api("/api/progress");
    if (p.cards_due > 0) {
      $("#nextReviewHint").textContent =
        `Aktuell ${p.cards_due} Karten fällig — Wiederholung am besten heute.`;
    } else {
      $("#nextReviewHint").textContent =
        "Nichts fällig. Vorschlag: in 2 Tagen eine kurze Wiederholung.";
    }
  } catch {}
}

// ---------- Wiederholungen ------------------------------
async function loadReview() {
  const list = $("#reviewList");
  list.innerHTML = "<p class='muted'>Lade …</p>";
  try {
    const cards = await api("/api/cards/due?limit=20");
    state.cards = cards;
    if (!cards.length) {
      list.innerHTML = "<p class='muted'>Keine fälligen Karten. Gut gepflegt. ✨</p>";
      return;
    }
    list.innerHTML = "";
    for (const c of cards) list.appendChild(renderCard(c));
  } catch (e) {
    list.innerHTML = `<p class="muted">Fehler: ${escapeHtml(e.message)}</p>`;
  }
}

function renderCard(card) {
  const wrap = document.createElement("div");
  wrap.className = "review-item";
  wrap.dataset.id = card.id;
  wrap.innerHTML = `
    <div class="head">
      <div class="front">${escapeHtml(card.front)}</div>
      <div class="topic-tag">${escapeHtml(card.topic)}</div>
    </div>
    <div class="question hidden"></div>
    <div class="back hidden" style="margin-top:8px;color:var(--muted)">
      <b>Antwort:</b> ${escapeHtml(card.back)}
    </div>
    <div class="row" style="margin-top:10px">
      <button class="ask">Frage zeigen</button>
      <button class="show ghost">Antwort zeigen</button>
    </div>
    <div class="row hidden" style="margin-top:10px">
      <span class="muted">Wie gut erinnert?</span>
      <div class="actions">
        <button class="q0" data-q="0">0</button>
        <button class="q1" data-q="1">1</button>
        <button class="q2" data-q="2">2</button>
        <button class="q3" data-q="3">3</button>
        <button class="q4" data-q="4">4</button>
        <button class="q5" data-q="5">5</button>
      </div>
    </div>
  `;
  wrap.querySelector(".ask").addEventListener("click", async () => {
    const qEl = wrap.querySelector(".question");
    qEl.classList.remove("hidden");
    if (state.pendingQuestions[card.id]) {
      qEl.textContent = state.pendingQuestions[card.id];
    } else {
      qEl.textContent = "Formuliere Frage …";
      try {
        const r = await api(`/api/cards/${card.id}/question`, { method: "POST" });
        state.pendingQuestions[card.id] = r.question;
        qEl.textContent = r.question;
      } catch (e) {
        qEl.textContent = "(Konnte keine Frage formulieren: " + e.message + ")";
      }
    }
    wrap.querySelector(".row:last-of-type").classList.remove("hidden");
  });
  wrap.querySelector(".show").addEventListener("click", () => {
    wrap.querySelector(".back").classList.remove("hidden");
  });
  wrap.querySelectorAll(".actions button").forEach((b) => {
    b.addEventListener("click", async () => {
      const q = Number(b.dataset.q);
      try {
        await api(`/api/cards/${card.id}/review`, {
          method: "POST",
          body: JSON.stringify({ quality: q }),
        });
        wrap.style.opacity = "0.4";
        wrap.style.pointerEvents = "none";
        toast(`Karte ${q >= 3 ? "eingeplant" : "zurückgesetzt"}.`, "ok");
        refreshDueBadge();
      } catch (e) {
        toast("Fehler: " + e.message, "error");
      }
    });
  });
  return wrap;
}

// ---------- Fortschritt ---------------------------------
async function loadProgress() {
  try {
    const p = await api("/api/progress");
    const grid = $("#progressGrid");
    grid.innerHTML = "";
    const stats = [
      ["Karten gesamt", p.cards_total],
      ["Davon gelernt", p.cards_learned],
      ["Aktuell fällig", p.cards_due],
      ["Wiederholungen", p.reviews_total],
      ["Sitzungen", p.sessions_total],
      ["Ø Antwortsicherheit", p.average_self_rating ?? "—"],
    ];
    for (const [k, v] of stats) {
      const el = document.createElement("div");
      el.className = "stat";
      el.innerHTML = `<div class="v">${v}</div><div class="k">${k}</div>`;
      grid.appendChild(el);
    }
    // Topic-Bars
    const total = Math.max(1, ...Object.values(p.by_topic));
    const ts = $("#topicStats");
    ts.innerHTML = "";
    for (const t of state.topics) {
      const c = p.by_topic[t.id] || 0;
      const pct = Math.round((c / total) * 100);
      const row = document.createElement("div");
      row.className = "topic-bar";
      row.innerHTML = `
        <div class="name">${t.label}</div>
        <div class="bar"><div style="width:${pct}%"></div></div>
        <div class="count">${c}</div>
      `;
      ts.appendChild(row);
    }
  } catch (e) {
    toast("Fortschritt laden fehlgeschlagen: " + e.message, "error");
  }
}

// ---------- Badges --------------------------------------
async function refreshDueBadge() {
  try {
    const p = await api("/api/progress");
    const b = $("#dueBadge");
    b.textContent = p.cards_due;
    b.classList.toggle("zero", p.cards_due === 0);
  } catch {}
}

// ---------- Hilfen --------------------------------------
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ---------- Init ----------------------------------------
(async function init() {
  try { await loadTopics(); } catch (e) { toast("Themen laden fehlgeschlagen.", "error"); }
  await refreshDueBadge();
  // History-Endpoint optional: versteckte Funktion
})();
