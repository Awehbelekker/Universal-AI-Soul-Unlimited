const STORAGE_KEY = "usa_pwa_settings_v1";
const DEFAULTS = {
  ollamaUrl: "http://127.0.0.1:11434",
  ollamaModel: "llama3.2:3b",
  speakReplies: true,
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
    if (!raw) return { ...DEFAULTS };
    const data = JSON.parse(raw);
    return {
      ollamaUrl: normalizeOllamaUrl(data.ollamaUrl || DEFAULTS.ollamaUrl),
      ollamaModel: (data.ollamaModel || DEFAULTS.ollamaModel).trim(),
      speakReplies:
        typeof data.speakReplies === "boolean"
          ? data.speakReplies
          : DEFAULTS.speakReplies,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function saveSettings(settings) {
  const next = {
    ollamaUrl: normalizeOllamaUrl(settings.ollamaUrl),
    ollamaModel: (settings.ollamaModel || DEFAULTS.ollamaModel).trim(),
    speakReplies: !!settings.speakReplies,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

const state = {
  settings: loadSettings(),
  busy: false,
  audio: null,
  voiceMeta: null,
};

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const modeLine = document.getElementById("modeLine");
const settingsBtn = document.getElementById("settingsBtn");
const dialog = document.getElementById("settingsDialog");
const settingsForm = document.getElementById("settingsForm");
const urlInput = document.getElementById("ollamaUrl");
const modelInput = document.getElementById("ollamaModel");
const speakInput = document.getElementById("speakReplies");
const voiceLine = document.getElementById("voiceLine");
const settingsStatus = document.getElementById("settingsStatus");
const testBtn = document.getElementById("testBtn");
const testVoiceBtn = document.getElementById("testVoiceBtn");

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
  speakInput.checked = !!state.settings.speakReplies;
  settingsStatus.textContent = "";
  settingsStatus.className = "status";
  refreshVoiceLine();
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
    const kind = data.cloning ? "clone" : data.tts_engine || "unknown";
    voiceLine.textContent = data.cloning
      ? `Voice PC: XTTS clone ready`
      : `Voice PC: ${kind} (${data.voice_id || "default"})`;
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

async function chat(message) {
  const payload = {
    model: state.settings.ollamaModel,
    prompt:
      "You are Universal Soul AI — a local-first personal companion for this user. " +
      "Universal Soul runs privately on their desktop/phone: chat via Ollama, optional voice, " +
      "memory/values, and careful automation. Prefer concise, helpful answers. " +
      "If asked what you are, explain that briefly without inventing unshipped features.\n\n" +
      `User: ${message}\n\nAssistant:`,
    stream: false,
    options: { num_predict: 256, temperature: 0.7 },
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
      body: JSON.stringify({ text, personality: "friendly" }),
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
    setMode(`${state.settings.ollamaModel} · speaking (${engine})`);
    await audio.play();
    audio.onended = () => {
      URL.revokeObjectURL(url);
      setMode(`${state.settings.ollamaModel} · ready`);
    };
  } catch (err) {
    addBubble("system", `Voice error: ${err.message}`);
  }
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
    addBubble("ai", reply);
    setMode(`${state.settings.ollamaModel} · ready`);
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
  settingsStatus.className = "status";
  settingsStatus.textContent = "Synthesizing on PC…";
  try {
    await speak("Hello from Universal Soul. This is my voice on your phone.");
    settingsStatus.className = "status ok";
    settingsStatus.textContent = "Voice played (check phone volume).";
  } catch (err) {
    settingsStatus.className = "status err";
    settingsStatus.textContent = String(err.message || err);
  }
});

settingsForm.addEventListener("submit", (e) => {
  const submitter = e.submitter;
  if (submitter && submitter.value === "cancel") return;
  e.preventDefault();
  state.settings = saveSettings({
    ollamaUrl: urlInput.value,
    ollamaModel: modelInput.value,
    speakReplies: speakInput.checked,
  });
  settingsStatus.className = "status ok";
  settingsStatus.textContent = "Saved locally on this device.";
  setMode(`${state.settings.ollamaModel} · saved`);
  dialog.close();
});

async function boot() {
  addBubble(
    "system",
    "Universal Soul thin client (PWA). Voice replies use your PC (Edge or clone)."
  );
  setMode(`${state.settings.ollamaModel} · checking`);
  await refreshVoiceLine();
  try {
    await probe();
    setMode(`${state.settings.ollamaModel} · ready`);
    addBubble("ai", "Connected to Ollama. Ask me anything.");
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
