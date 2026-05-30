// app.js — vanilla-JS chat client for the SHL Assessment Recommender.
// The server is STATELESS, so this file keeps the running conversation in
// `messages` and resends the whole history on every POST /chat.

const $ = (id) => document.getElementById(id);
const DEFAULT_MODELS = {
  groq: "llama-3.3-70b-versatile",
  gemini: "gemini-2.5-flash",
  openrouter: "meta-llama/llama-3.3-70b-instruct:free",
};
const MAX_TURNS = 8;

let messages = [];          // [{role, content}] — stateless history
let ended = false;
let serverLlmReady = false; // true if the server already has its own LLM key

/* ---------- Settings drawer (only used if server lacks a key) -------------- */
function setStatus(msg) { $("keyStatus").textContent = msg; }

function loadSettings() {
  $("provider").value = localStorage.getItem("shl_provider") || "gemini";
  $("model").value = localStorage.getItem("shl_model") || "";
  $("apiKey").value = localStorage.getItem("shl_key") || "";
  if ($("apiKey").value) setStatus("Key loaded from this browser.");
  $("model").placeholder = DEFAULT_MODELS[$("provider").value] || "auto";
}

$("provider").addEventListener("change", () => {
  $("model").placeholder = DEFAULT_MODELS[$("provider").value] || "auto";
});
$("saveKey").addEventListener("click", () => {
  localStorage.setItem("shl_provider", $("provider").value);
  localStorage.setItem("shl_model", $("model").value.trim());
  localStorage.setItem("shl_key", $("apiKey").value.trim());
  setStatus($("apiKey").value.trim() ? "Saved." : "Cleared.");
});
$("settingsBtn").addEventListener("click", () => {
  const d = $("settings");
  d.hidden = !d.hidden;
});

/* ---------- Rendering ------------------------------------------------------ */
function ensureChatVisible() {
  if ($("hero").hidden) return;
  $("hero").hidden = true;
  $("chat").hidden = false;
}

function addBubble(role, text, who) {
  ensureChatVisible();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role === "user" ? "user" : "bot"}`;
  const b = document.createElement("div");
  b.className = "bubble";
  if (who) {
    const w = document.createElement("span");
    w.className = "who"; w.textContent = who;
    b.appendChild(w);
  }
  const t = document.createElement("span");
  t.textContent = text;
  b.appendChild(t);
  wrap.appendChild(b);
  $("chat").appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addRecommendations(recs) {
  if (!recs || !recs.length) return;
  const last = $("chat").lastElementChild;
  if (!last) return;
  const grid = document.createElement("div");
  grid.className = "recs";
  for (const r of recs) {
    const card = document.createElement("div");
    card.className = "rec";
    card.innerHTML =
      `<a href="${r.url}" target="_blank" rel="noopener">${r.name}</a>` +
      `<span class="badge">${r.test_type || "—"}</span>`;
    grid.appendChild(card);
  }
  last.querySelector(".bubble").appendChild(grid);
  scrollToBottom();
}

function addCompleteBanner() {
  const banner = document.createElement("div");
  banner.className = "complete";
  banner.innerHTML = `<span aria-hidden="true">✓</span> Assessment battery complete`;
  $("chat").appendChild(banner);
  scrollToBottom();
}

// Three bouncing dots while the assistant is thinking (matches the reference UX)
function addTypingDots() {
  ensureChatVisible();
  const wrap = document.createElement("div");
  wrap.className = "msg bot";
  const b = document.createElement("div");
  b.className = "bubble typing-bubble";
  b.innerHTML = '<span class="d"></span><span class="d"></span><span class="d"></span>';
  wrap.appendChild(b);
  $("chat").appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function scrollToBottom() {
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
}

function updateTurnMeter() {
  if (!messages.length) { $("turnMeter").textContent = ""; return; }
  const left = Math.max(0, MAX_TURNS - messages.length);
  $("turnMeter").textContent =
    `turn ${messages.length}/${MAX_TURNS}` + (left <= 2 && left > 0 ? " · wrapping up" : "");
}

/* ---------- Composer ------------------------------------------------------- */
const input = $("input");

function autoGrow() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
}
input.addEventListener("input", autoGrow);
input.addEventListener("keydown", (e) => {
  // Enter sends, Shift+Enter inserts a newline
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  send(input.value);
});

document.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (chip) send(chip.dataset.q);
});

async function send(text) {
  text = (text || "").trim();
  if (ended || !text) return;
  const key = localStorage.getItem("shl_key");
  if (!key && !serverLlmReady) {
    $("settings").hidden = false;
    setStatus("⚠ Add an API key first.");
    return;
  }

  messages.push({ role: "user", content: text });
  addBubble("user", text);
  input.value = ""; autoGrow();
  updateTurnMeter();
  $("send").disabled = true;

  const thinking = addTypingDots();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-LLM-Provider": localStorage.getItem("shl_provider") || "",
        "X-LLM-Api-Key": key || "",
        "X-LLM-Model": localStorage.getItem("shl_model") || "",
      },
      body: JSON.stringify({ messages }),
    });
    const data = await res.json();
    thinking.remove();

    addBubble("bot", data.reply || "(no reply)", "Assistant");
    addRecommendations(data.recommendations);
    messages.push({ role: "assistant", content: data.reply || "" });
    updateTurnMeter();

    if (data.end_of_conversation) {
      ended = true;
      addCompleteBanner();
    }
  } catch (e) {
    thinking.remove();
    addBubble("bot", "Network error talking to the service: " + e.message, "Assistant");
  } finally {
    $("send").disabled = ended;
  }
}

/* ---------- Init ----------------------------------------------------------- */
(async function init() {
  loadSettings();
  autoGrow();
  updateTurnMeter();
  try {
    const cfg = await (await fetch("/config")).json();
    serverLlmReady = !!cfg.server_llm_ready;
    if (!serverLlmReady) {
      $("settings").hidden = false;       // prompt for key when server has none
      $("status").innerHTML = '<span class="ring" style="background:#f59e0b"></span> needs API key';
    }
  } catch { /* ignore */ }
})();
