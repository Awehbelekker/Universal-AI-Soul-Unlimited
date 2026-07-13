const STORAGE_KEY = "usa_pwa_settings_v2";
const HISTORY_KEY = "usa_pwa_history_v1";
const DEFAULTS = {
  ollamaUrl: "http://127.0.0.1:11434",
  ollamaModel: "llama3.2:3b",
  speakReplies: true,
  companionName: "Universal Soul",
  tone: "friendly",
};

const TONE_HINTS = {
  friendly: "warm, supportive, conversational",
  professional: "clear, concise, businesslike",
  calm: "gentle, steady, unhurried",
  energetic: "upbeat, motivating, lively",
  creative: "imaginative, playful, metaphorical when useful",
  analytical: "precise, structured, reason step-by-step briefly",
};

function normalizeOllamaUrl(raw) {
  let u = (raw || "").trim();
  if (!u) return DEFAULTS.ollamaUrl;
  if (!u.includes("://")) u = "http://" + u;
  u = u.replace(/\/$/, "");
  try {
    const parsed = new URL(u);
    const host = parsed.hostname;
    const port = parsed.port || "11434";
    return `${parsed.protocol}//${host}:${port}`;
  } catch {
    return DEFAULTS.ollamaUrl;
  }
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    // migrate v1
    const legacy = !raw ? localStorage.getItem("usa_pwa_settings_v1") : null;
    const data = JSON.parse(raw || legacy || "{}");
    const tone = (data.tone || DEFAULTS.tone).toLowerCase();
    return {
      ollamaUrl: normalizeOllamaUrl(data.ollamaUrl || DEFAULTS.ollamaUrl),
      ollamaModel: (data.ollamaModel || DEFAULTS.ollamaModel).trim(),
      speakReplies:
        typeof data.speakReplies === "boolean"
          ? data.speakReplies
          : DEFAULTS.speakReplies,
      companionName: (data.companionName || DEFAULTS.companionName).trim() ||
        DEFAULTS.companionName,
      tone: TONE_HINTS[tone] ? tone : DEFAULTS.tone,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function saveSettings(settings) {
  const tone = (settings.tone || DEFAULTS.tone).toLowerCase();
  const next = {
    ollamaUrl: normalizeOllamaUrl(settings.ollamaUrl),
    ollamaModel: (settings.ollamaModel || DEFAULTS.ollamaModel).trim(),
    speakReplies: !!settings.speakReplies,
    companionName:
      (settings.companionName || DEFAULTS.companionName).trim() ||
      DEFAULTS.companionName,
    tone: TONE_HINTS[tone] ? tone : DEFAULTS.tone,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const data = raw ? JSON.parse(raw) : [];
    return Array.isArray(data) ? data.slice(-20) : [];
  } catch {
    return [];
  }
}

function saveHistory(history) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-20)));
}

const state = {
  settings: loadSettings(),
  history: loadHistory(),
  busy: false,
  audio: null,
  voiceMeta: null,
};

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const modeLine = document.getElementById("modeLine");
const brandName = document.getElementById("brandName");
const settingsBtn = document.getElementById("settingsBtn");
const dialog = document.getElementById("settingsDialog");
const settingsForm = document.getElementById("settingsForm");
const urlInput = document.getElementById("ollamaUrl");
const modelInput = document.getElementById("ollamaModel");
const nameInput = document.getElementById("companionName");
const toneInput = document.getElementById("tone");
const speakInput = document.getElementById("speakReplies");
const voiceLine = document.getElementById("voiceLine");
const settingsStatus = document.getElementById("settingsStatus");
const testBtn = document.getElementById("testBtn");
const testVoiceBtn = document.getElementById("testVoiceBtn");
const clearChatBtn = document.getElementById("clearChatBtn");

function companionLabel() {
  return state.settings.companionName || "Universal Soul";
}

function applyBrand() {
  const name = companionLabel();
  brandName.textContent = name;
  document.title = name;
}

function addBubble(role, text) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function setMode(text) {
  modeLine.textContent = text;
}

function fillSettingsForm() {
  urlInput.value = state.settings.ollamaUrl;
  modelInput.value = state.settings.ollamaModel;
  nameInput.value = state.settings.companionName;
  toneInput.value = state.settings.tone;
  speakInput.checked = !!state.settings.speakReplies;
  settingsStatus.textContent = "";
  settingsStatus.className = "status";
  refreshVoiceLine();
}

function systemPrompt() {
  const name = companionLabel();
  const tone = state.settings.tone;
  const hint = TONE_HINTS[tone] || TONE_HINTS.friendly;
  return (
    `You are ${name}, the user's Universal Soul companion — a local-first personal AI. ` +
    `Your name is ${name}. Speak in a ${tone} tone (${hint}). ` +
    "You run privately on their desktop/phone via Ollama, with optional voice and careful automation. " +
    "Use prior conversation turns for continuity — do not repeat the same greeting or generic offer every time. " +
    "Prefer concise, varied, helpful answers. Do not invent unshipped features."
  );
}

async function syncProfileFromPc() {
  try {
    const res = await fetch("/api/profile");
    const data = await res.json();
    if (!data.ok) return;
    let changed = false;
    // Prefer PC profile when local still has defaults
    if (
      (!localStorage.getItem(STORAGE_KEY) &&
        !localStorage.getItem("usa_pwa_settings_v1")) ||
      state.settings.companionName === DEFAULTS.companionName
    ) {
      if (data.companion_name) {
        state.settings.companionName = data.companion_name;
        changed = true;
      }
    }
    if (data.tone && TONE_HINTS[data.tone]) {
      // Only overwrite tone if never customized locally after migrate
      if (!localStorage.getItem(STORAGE_KEY + ":tone_set")) {
        state.settings.tone = data.tone;
        changed = true;
      }
    }
    if (changed) {
      state.settings = saveSettings(state.settings);
      applyBrand();
    }
  } catch {
    /* offline PC profile is optional */
  }
}

async function pushProfileToPc() {
  try {
    await fetch("/api/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        companion_name: state.settings.companionName,
        tone: state.settings.tone,
      }),
    });
  } catch {
    /* best-effort sync */
  }
}

async function refreshVoiceLine() {
  try {
    const res = await fetch("/api/voice-status");
    const data = await res.json();
    state.voiceMeta = data;
    if (!data.ok) {
      voiceLine.textContent = `Voice PC: unavailable (${data.error || "error"})`;
      return;
    }
    voiceLine.textContent = data.cloning
      ? `Voice PC: XTTS clone ready (your sample)`
      : `Voice PC: Edge ${data.voice_id || "neural"} — clone optional on desktop`;
  } catch (err) {
    voiceLine.textContent = `Voice PC: unreachable (${err.message})`;
  }
}

async function proxyFetch(path, options = {}) {
  const target = normalizeOllamaUrl(state.settings.ollamaUrl);
  const headers = {
    "Content-Type": "application/json",
    "X-Ollama-URL": target,
    ...(options.headers || {}),
  };
  return fetch(path, { ...options, headers });
}

async function probe() {
  const res = await proxyFetch("/proxy/api/tags", { method: "GET" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

function buildPrompt(message) {
  const parts = [systemPrompt(), ""];
  for (const turn of state.history.slice(-12)) {
    parts.push(`${turn.role === "user" ? "User" : companionLabel()}: ${turn.text}`);
  }
  parts.push(`User: ${message}`);
  parts.push(`${companionLabel()}:`);
  return parts.join("\n");
}

async function chat(message) {
  const payload = {
    model: state.settings.ollamaModel,
    prompt: buildPrompt(message),
    stream: false,
    options: { num_predict: 320, temperature: 0.85 },
  };
  const res = await proxyFetch("/proxy/api/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return (data.response || "").trim() || "(empty response)";
}

async function speak(text) {
  if (!text || !state.settings.speakReplies) return;
  try {
    const res = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        personality: state.settings.tone || "friendly",
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    if (state.audio) {
      state.audio.pause();
      URL.revokeObjectURL(state.audio.src);
    }
    const audio = new Audio(url);
    state.audio = audio;
    const engine = res.headers.get("X-Soul-TTS-Engine") || "tts";
    setMode(`${companionLabel()} · speaking (${engine})`);
    await audio.play();
    audio.onended = () => {
      URL.revokeObjectURL(url);
      setMode(`${companionLabel()} · ready`);
    };
  } catch (err) {
    addBubble("system", `Voice error: ${err.message}`);
  }
}

function clearChat() {
  state.history = [];
  saveHistory(state.history);
  chatEl.innerHTML = "";
  addBubble("system", `Chat cleared. ${companionLabel()} is listening fresh.`);
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message || state.busy) return;
  state.busy = true;
  sendBtn.disabled = true;
  inputEl.value = "";
  addBubble("user", message);
  setMode("Thinking…");
  try {
    const reply = await chat(message);
    state.history.push({ role: "user", text: message });
    state.history.push({ role: "assistant", text: reply });
    saveHistory(state.history);
    addBubble("ai", reply);
    setMode(`${companionLabel()} · ready`);
    await speak(reply);
  } catch (err) {
    addBubble("system", `Ollama error: ${err.message}`);
    setMode("Offline / demo");
  } finally {
    state.busy = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
});

settingsBtn.addEventListener("click", () => {
  fillSettingsForm();
  dialog.showModal();
});

testBtn.addEventListener("click", async () => {
  state.settings = {
    ...state.settings,
    ollamaUrl: urlInput.value,
    ollamaModel: modelInput.value,
    companionName: nameInput.value,
    tone: toneInput.value,
    speakReplies: speakInput.checked,
  };
  settingsStatus.className = "status";
  settingsStatus.textContent = "Testing…";
  try {
    const data = await probe();
    const models = (data.models || []).map((m) => m.name).filter(Boolean);
    settingsStatus.className = "status ok";
    settingsStatus.textContent =
      `OK — ${(models.slice(0, 5).join(", ") || "no models listed")}`;
    setMode(`Reachable · ${state.settings.ollamaModel}`);
  } catch (err) {
    settingsStatus.className = "status err";
    settingsStatus.textContent = String(err.message || err);
    setMode("Unreachable");
  }
});

testVoiceBtn.addEventListener("click", async () => {
  state.settings.speakReplies = true;
  speakInput.checked = true;
  state.settings.tone = toneInput.value || state.settings.tone;
  state.settings.companionName =
    nameInput.value.trim() || state.settings.companionName;
  applyBrand();
  settingsStatus.className = "status";
  settingsStatus.textContent = "Synthesizing on PC…";
  try {
    await speak(
      `Hello — I'm ${companionLabel()}. This is my ${state.settings.tone} voice on your phone.`
    );
    settingsStatus.className = "status ok";
    settingsStatus.textContent = "Voice played (check phone volume).";
  } catch (err) {
    settingsStatus.className = "status err";
    settingsStatus.textContent = String(err.message || err);
  }
});

clearChatBtn.addEventListener("click", () => {
  clearChat();
  settingsStatus.className = "status ok";
  settingsStatus.textContent = "Chat history cleared.";
});

settingsForm.addEventListener("submit", (e) => {
  const submitter = e.submitter;
  if (submitter && submitter.value === "cancel") return;
  e.preventDefault();
  state.settings = saveSettings({
    ollamaUrl: urlInput.value,
    ollamaModel: modelInput.value,
    companionName: nameInput.value,
    tone: toneInput.value,
    speakReplies: speakInput.checked,
  });
  localStorage.setItem(STORAGE_KEY + ":tone_set", "1");
  applyBrand();
  pushProfileToPc();
  settingsStatus.className = "status ok";
  settingsStatus.textContent = "Saved locally + synced to PC profile.";
  setMode(`${companionLabel()} · saved`);
  dialog.close();
});

async function boot() {
  applyBrand();
  await syncProfileFromPc();
  applyBrand();
  addBubble(
    "system",
    `${companionLabel()} thin client. Set a name & tone in Settings. Voice uses your PC (Edge or clone).`
  );
  setMode(`${companionLabel()} · checking`);
  await refreshVoiceLine();
  try {
    await probe();
    setMode(`${companionLabel()} · ready`);
    if (state.history.length) {
      addBubble(
        "system",
        `Restored ${state.history.length} recent turns. Say hello or continue.`
      );
    } else {
      addBubble("ai", `Hi — I'm ${companionLabel()}. What's on your mind?`);
    }
  } catch (err) {
    setMode("Offline — open Settings");
    addBubble(
      "system",
      `Not connected yet (${err.message}). Start Ollama on the PC and set the LAN URL.`
    );
  }

  if ("serviceWorker" in navigator) {
    try {
      await navigator.serviceWorker.register("./sw.js");
    } catch {
      /* optional */
    }
  }
}

boot();
