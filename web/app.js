const STORAGE_KEY = "usa_pwa_settings_v2";
const HISTORY_KEY = "usa_pwa_history_v1";
const GOOGLE_BANNER_KEY = "usa_google_banner_dismissed";
const DEFAULTS = {
  ollamaUrl: "http://127.0.0.1:11434",
  ollamaModel: "llama3.2:3b",
  speakReplies: true,
  companionName: "Universal Soul",
  tone: "friendly",
  voiceId: "auto",
  kokoroVoice: "af_heart",
  voiceTempo: 0,
  voicePitch: 0,
  // Voice engine for spoken replies:
  //  "natural"   - Kokoro-82M, natural + fully offline (mobile default)
  //  "fast"      - fast Edge neural (Jenny), online
  //  "authentic" - your cloned voice via XTTS (may be slow)
  //  "auto"      - authentic clone, but fall back to fast Edge if it lags
  voiceEngine: "natural",
  theme: "auto",
};

const VOICE_ENGINES = ["natural", "fast", "authentic", "auto"];
// If a clone chunk takes longer than this, "auto" mode drops to fast Edge for
// the rest of the reply so speech stays responsive.
const CLONE_LAG_MS = 12000;

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
      voiceId: (data.voiceId || DEFAULTS.voiceId).trim() || DEFAULTS.voiceId,
      kokoroVoice:
        (data.kokoroVoice || DEFAULTS.kokoroVoice).trim() ||
        DEFAULTS.kokoroVoice,
      voiceEngine: VOICE_ENGINES.includes(data.voiceEngine)
        ? data.voiceEngine
        : DEFAULTS.voiceEngine,
      voiceTempo: clampInt(data.voiceTempo, -20, 20, DEFAULTS.voiceTempo),
      voicePitch: clampInt(data.voicePitch, -10, 10, DEFAULTS.voicePitch),
      theme: ["auto", "dark", "light"].includes(data.theme)
        ? data.theme
        : DEFAULTS.theme,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function clampInt(v, lo, hi, fallback) {
  const n = Number(v);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(lo, Math.min(hi, Math.round(n)));
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
    voiceId: (settings.voiceId || DEFAULTS.voiceId).trim() || DEFAULTS.voiceId,
    kokoroVoice:
      (settings.kokoroVoice || DEFAULTS.kokoroVoice).trim() ||
      DEFAULTS.kokoroVoice,
    voiceEngine: VOICE_ENGINES.includes(settings.voiceEngine)
      ? settings.voiceEngine
      : DEFAULTS.voiceEngine,
    voiceTempo: clampInt(settings.voiceTempo, -20, 20, DEFAULTS.voiceTempo),
    voicePitch: clampInt(settings.voicePitch, -10, 10, DEFAULTS.voicePitch),
    theme: ["auto", "dark", "light"].includes(settings.theme)
      ? settings.theme
      : DEFAULTS.theme,
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
  lastSpeak: "",
  lastTools: [],
  lastAiBubble: null,
  speakGen: 0,
  audioUnlocked: false,
  memberId: localStorage.getItem("usa_member_id") || "primary",
  online: navigator.onLine,
  offlinePack: null,
  family: null,
};

const chatEl = document.getElementById("chat");
const chatEmpty = document.getElementById("chatEmpty");
const emptyName = document.getElementById("emptyName");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const chatMicBtn = document.getElementById("chatMicBtn");
const chatNoteBtn = document.getElementById("chatNoteBtn");
const chatNoteFile = document.getElementById("chatNoteFile");
const modeLine = document.getElementById("modeLine");
const brandName = document.getElementById("brandName");
const statusStrip = document.getElementById("statusStrip");
const statusStripText = document.getElementById("statusStripText");
const menuBtn = document.getElementById("menuBtn");
const menuDialog = document.getElementById("menuDialog");
const menuSettingsBtn = document.getElementById("menuSettingsBtn");
const menuFamilyBtn = document.getElementById("menuFamilyBtn");
const menuInviteBtn = document.getElementById("menuInviteBtn");
const menuCloseBtn = document.getElementById("menuCloseBtn");
const settingsFamilyBtn = document.getElementById("settingsFamilyBtn");
const themeSelect = document.getElementById("themeSelect");
const dialog = document.getElementById("settingsDialog");
const settingsForm = document.getElementById("settingsForm");
const urlInput = document.getElementById("ollamaUrl");
const modelInput = document.getElementById("ollamaModel");
const nameInput = document.getElementById("companionName");
const toneInput = document.getElementById("tone");
const speakInput = document.getElementById("speakReplies");
const voiceLine = document.getElementById("voiceLine");
const voiceIdInput = document.getElementById("voiceId");
const kokoroVoiceInput = document.getElementById("kokoroVoice");
const voiceEngineInput = document.getElementById("voiceEngine");
const voiceTempoInput = document.getElementById("voiceTempo");
const voicePitchInput = document.getElementById("voicePitch");
const tempoVal = document.getElementById("tempoVal");
const pitchVal = document.getElementById("pitchVal");
const cloneFile = document.getElementById("cloneFile");
const cloneUploadBtn = document.getElementById("cloneUploadBtn");
const cloneRecordBtn = document.getElementById("cloneRecordBtn");
const cloneRecordTimer = document.getElementById("cloneRecordTimer");
const clonePreview = document.getElementById("clonePreview");
const cloneDemoBtn = document.getElementById("cloneDemoBtn");
const cloneClearBtn = document.getElementById("cloneClearBtn");
const cloneStatus = document.getElementById("cloneStatus");
const remoteLine = document.getElementById("remoteLine");

const cloneRec = {
  recorder: null,
  stream: null,
  chunks: [],
  startedAt: 0,
  tick: null,
  mime: "audio/webm",
};
const remoteUrls = document.getElementById("remoteUrls");
const remoteRefreshBtn = document.getElementById("remoteRefreshBtn");
const settingsStatus = document.getElementById("settingsStatus");
const testBtn = document.getElementById("testBtn");
const testVoiceBtn = document.getElementById("testVoiceBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const googleLine = document.getElementById("googleLine");
const googleConnectBtn = document.getElementById("googleConnectBtn");
const googleDisconnectBtn = document.getElementById("googleDisconnectBtn");
const googleBanner = document.getElementById("googleBanner");
const googleBannerBtn = document.getElementById("googleBannerBtn");
const googleBannerDismiss = document.getElementById("googleBannerDismiss");
const googleBannerTitle = document.getElementById("googleBannerTitle");
const googleBannerHint = document.getElementById("googleBannerHint");
const gmailComposeBtn = document.getElementById("gmailComposeBtn");
const driveNoteBtn = document.getElementById("driveNoteBtn");
const gmailDialog = document.getElementById("gmailDialog");
const gmailForm = document.getElementById("gmailForm");
const gmailTo = document.getElementById("gmailTo");
const gmailSubject = document.getElementById("gmailSubject");
const gmailBody = document.getElementById("gmailBody");
const gmailStatus = document.getElementById("gmailStatus");
const gmailDraftBtn = document.getElementById("gmailDraftBtn");
const gmailSendBtn = document.getElementById("gmailSendBtn");
const toolChipsEl = document.getElementById("toolChips");

state.tools = [];
state.google = null;

const offlineBanner = document.getElementById("offlineBanner");
const memberSelect = document.getElementById("memberSelect");
const familyDialog = document.getElementById("familyDialog");
const familyEnabled = document.getElementById("familyEnabled");
const householdName = document.getElementById("householdName");
const familyValues = document.getElementById("familyValues");
const familyBoundaries = document.getElementById("familyBoundaries");
const memberName = document.getElementById("memberName");
const memberRole = document.getElementById("memberRole");
const memberPin = document.getElementById("memberPin");
const boardFact = document.getElementById("boardFact");
const reminderText = document.getElementById("reminderText");
const familyStatus = document.getElementById("familyStatus");
const reminderList = document.getElementById("reminderList");
const familySaveBtn = document.getElementById("familySaveBtn");
const memberAddBtn = document.getElementById("memberAddBtn");
const boardAddBtn = document.getElementById("boardAddBtn");
const reminderAddBtn = document.getElementById("reminderAddBtn");
const onboard = document.getElementById("onboard");
const onboardStepLabel = document.getElementById("onboardStepLabel");
const onboardTitle = document.getElementById("onboardTitle");
const onboardHint = document.getElementById("onboardHint");
const onboardPaneWelcome = document.getElementById("onboardPaneWelcome");
const onboardPaneName = document.getElementById("onboardPaneName");
const onboardPaneGoogle = document.getElementById("onboardPaneGoogle");
const onboardPaneInvite = document.getElementById("onboardPaneInvite");
const onboardName = document.getElementById("onboardName");
const onboardTone = document.getElementById("onboardTone");
const onboardHouse = document.getElementById("onboardHouse");
const onboardGoogleBtn = document.getElementById("onboardGoogleBtn");
const onboardGoogleSkip = document.getElementById("onboardGoogleSkip");
const onboardGoogleStatus = document.getElementById("onboardGoogleStatus");
const onboardInviteRole = document.getElementById("onboardInviteRole");
const onboardInviteHint = document.getElementById("onboardInviteHint");
const onboardMakeInvite = document.getElementById("onboardMakeInvite");
const onboardQrBox = document.getElementById("onboardQrBox");
const onboardQrImg = document.getElementById("onboardQrImg");
const onboardInviteUrl = document.getElementById("onboardInviteUrl");
const onboardCopyInvite = document.getElementById("onboardCopyInvite");
const onboardBack = document.getElementById("onboardBack");
const onboardNext = document.getElementById("onboardNext");
const joinInvite = document.getElementById("joinInvite");
const joinHint = document.getElementById("joinHint");
const joinName = document.getElementById("joinName");
const joinPin = document.getElementById("joinPin");
const joinStatus = document.getElementById("joinStatus");
const joinCancel = document.getElementById("joinCancel");
const joinSubmit = document.getElementById("joinSubmit");
const familyInviteBtn = document.getElementById("familyInviteBtn");
const familyInviteRole = document.getElementById("familyInviteRole");
const familyQrBox = document.getElementById("familyQrBox");
const familyQrImg = document.getElementById("familyQrImg");
const familyInviteUrl = document.getElementById("familyInviteUrl");
const onboardWhatsApp = document.getElementById("onboardWhatsApp");
const onboardShare = document.getElementById("onboardShare");
const familyCopyInvite = document.getElementById("familyCopyInvite");
const familyWhatsApp = document.getElementById("familyWhatsApp");
const familyShare = document.getElementById("familyShare");
const googleSetupBox = document.getElementById("googleSetupBox");
const googleClientId = document.getElementById("googleClientId");
const googleClientSecret = document.getElementById("googleClientSecret");
const googleSaveCredsBtn = document.getElementById("googleSaveCredsBtn");
const googleSetupStatus = document.getElementById("googleSetupStatus");
const googleRedirectHint = document.getElementById("googleRedirectHint");
const onboardGoogleSetup = document.getElementById("onboardGoogleSetup");
const onboardClientId = document.getElementById("onboardClientId");
const onboardClientSecret = document.getElementById("onboardClientSecret");
const onboardSaveCreds = document.getElementById("onboardSaveCreds");

const ONBOARD_KEY = "usa_onboard_done_v1";
let onboardStep = 0;
let pendingInviteToken = null;
let lastInviteUrl = "";

function inviteShareText(url) {
  return (
    "Link your device to our Universal Soul household (same Wi‑Fi as the PC):\n" +
    (url || "")
  );
}

function openWhatsAppShare(url) {
  const text = inviteShareText(url);
  const wa = "https://wa.me/?text=" + encodeURIComponent(text);
  window.open(wa, "_blank", "noopener,noreferrer");
}

async function nativeShareInvite(url) {
  const text = inviteShareText(url);
  if (navigator.share) {
    try {
      await navigator.share({
        title: "Universal Soul — link device",
        text,
        url,
      });
      return true;
    } catch (err) {
      if (err && err.name === "AbortError") return false;
    }
  }
  // Fallback: copy
  try {
    await navigator.clipboard.writeText(url);
    return "copied";
  } catch {
    return false;
  }
}

function setOfflineUi(offline) {
  state.online = !offline;
  if (offlineBanner) offlineBanner.hidden = !offline;
  if (offline && googleBanner) googleBanner.hidden = true;
  if (offline) setMode(`${companionLabel()} · offline light`);
  if (formEl) formEl.classList.toggle("is-busy", !!state.busy);
}

function applyTheme(theme) {
  const t = theme || "auto";
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
}

function canShowGoogleBanner() {
  if (localStorage.getItem(GOOGLE_BANNER_KEY)) return false;
  if (!navigator.onLine || state.online === false) return false;
  return true;
}

function showGoogleBanner(show) {
  if (!googleBanner) return;
  googleBanner.hidden = !show || !canShowGoogleBanner();
}

function openSettings(tab) {
  fillSettingsForm();
  if (tab) selectSettingsTab(tab);
  openSheet(dialog);
}

function selectSettingsTab(tabId) {
  if (!settingsForm) return;
  const tabs = settingsForm.querySelectorAll('.settings-tabs [role="tab"]');
  const panels = settingsForm.querySelectorAll(".settings-panel");
  tabs.forEach((tab) => {
    const on = tab.dataset.tab === tabId;
    tab.setAttribute("aria-selected", on ? "true" : "false");
  });
  panels.forEach((panel) => {
    panel.hidden = panel.dataset.panel !== tabId;
  });
}

function initSettingsTabs() {
  if (!settingsForm) return;
  settingsForm.querySelectorAll('.settings-tabs [role="tab"]').forEach((tab) => {
    tab.addEventListener("click", () => selectSettingsTab(tab.dataset.tab || "companion"));
  });
}

function initStarterChips() {
  document.querySelectorAll("#starterChips [data-prompt]").forEach((btn) => {
    btn.addEventListener("click", () => sendChatMessage(btn.dataset.prompt || ""));
  });
}

function openMenuSheet() {
  refreshFamily();
  openSheet(menuDialog);
}

async function refreshOfflinePack() {
  try {
    const res = await fetch("/api/offline-pack");
    const data = await res.json();
    state.offlinePack = data;
    localStorage.setItem("usa_offline_pack", JSON.stringify(data));
  } catch {
    try {
      state.offlinePack = JSON.parse(localStorage.getItem("usa_offline_pack") || "null");
    } catch {
      state.offlinePack = null;
    }
  }
}

function localLightReply(message) {
  const pack = state.offlinePack || {};
  const faq = pack.faq || [];
  const low = (message || "").toLowerCase();
  for (const item of faq) {
    if (item.q && low.includes(String(item.q).toLowerCase())) return item.a;
  }
  const name = (pack.profile && pack.profile.companion_name) || companionLabel();
  return (
    (pack.canned && pack.canned.no_pc) ||
    `${name} offline light: cached only. You said “${String(message).slice(0, 160)}”.`
  );
}

async function refreshFamily() {
  try {
    const res = await fetch("/api/family");
    const data = await res.json();
    state.family = data;
    if (memberSelect) {
      memberSelect.innerHTML = "";
      const members = data.members || [{ id: "primary", display_name: "Me" }];
      for (const m of members) {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = `${m.display_name || m.id} (${m.role || "member"})`;
        memberSelect.appendChild(opt);
      }
      memberSelect.value = state.memberId;
      if (memberSelect.value !== state.memberId) {
        state.memberId = memberSelect.value || "primary";
      }
    }
    if (familyEnabled) familyEnabled.checked = !!data.enabled;
    if (householdName) householdName.value = data.name || "";
    if (familyValues) familyValues.value = (data.shared_values || []).join(", ");
    if (familyBoundaries)
      familyBoundaries.value = (data.boundaries || []).join(", ");
  } catch {
    /* optional while offline */
  }
  await refreshReminders();
}

async function refreshReminders() {
  if (!reminderList) return;
  try {
    const res = await fetch("/api/family/reminders");
    const data = await res.json();
    const items = data.reminders || [];
    reminderList.textContent = items.length
      ? "Open: " + items.map((r) => r.text).slice(0, 5).join(" · ")
      : "No open reminders.";
  } catch {
    reminderList.textContent = "";
  }
}

async function syncSharedHistory() {
  try {
    const res = await fetch(
      `/api/memory?member_id=${encodeURIComponent(state.memberId)}`
    );
    const data = await res.json();
    if (!data.ok || !Array.isArray(data.turns)) return;
    const turns = data.turns
      .filter((t) => t.role === "user" || t.role === "assistant")
      .map((t) => ({ role: t.role, text: t.text }));
    if (turns.length) {
      state.history = turns.slice(-20);
      saveHistory(state.history);
    }
  } catch {
    /* keep local */
  }
}

function companionLabel() {
  return state.settings.companionName || "Universal Soul";
}

function applyBrand() {
  const name = companionLabel();
  brandName.textContent = name;
  document.title = name;
  if (emptyName) emptyName.textContent = name;
}

function syncChatEmpty() {
  if (!chatEmpty || !chatEl) return;
  const hasBubbles =
    !!chatEl.querySelector(".bubble-row") || !!chatEl.querySelector(".bubble");
  chatEmpty.hidden = hasBubbles;
}

function companionInitial() {
  const n = companionLabel();
  return (n.charAt(0) || "S").toUpperCase();
}

function toolPillLabel(t) {
  const map = {
    web_search: "search",
    weather: "weather",
    thinkmesh: "deep think",
    gmail: "email",
    drive: "drive",
  };
  return map[t.tool] || t.tool || "tool";
}

function buildToolPills(tools) {
  const list = (tools || []).filter((t) => t && t.tool !== "thinkmesh");
  if (!list.length) return null;
  const box = document.createElement("details");
  box.className = "tool-pills";
  const sum = document.createElement("summary");
  const labels = list.map(toolPillLabel);
  sum.textContent =
    labels.length === 1 ? `Used ${labels[0]}` : `Used ${labels.length} tools`;
  box.appendChild(sum);
  const details = document.createElement("div");
  details.className = "tool-pill-details";
  for (const t of list) {
    const p = document.createElement("p");
    p.textContent = t.ok
      ? `${t.tool}: ${(t.summary || "").slice(0, 280)}`
      : `${t.tool} failed: ${t.error || "error"}`;
    details.appendChild(p);
  }
  box.appendChild(details);
  return box;
}

function addBubble(role, text, extra = {}) {
  if (role === "user") {
    const row = document.createElement("div");
    row.className = "bubble-row user-row";
    const bubble = document.createElement("div");
    bubble.className = "bubble user";
    bubble.textContent = text;
    row.appendChild(bubble);
    chatEl.appendChild(row);
  } else if (role === "ai") {
    const row = document.createElement("div");
    row.className = "bubble-row ai-row";
    const avatar = document.createElement("span");
    avatar.className = "bubble-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = companionInitial();
    const stack = document.createElement("div");
    stack.className = "bubble-stack";
    const bubble = document.createElement("div");
    bubble.className = "bubble ai";
    bubble.textContent = text;
    stack.appendChild(bubble);
    const pills = buildToolPills(extra.tools || []);
    if (pills) stack.appendChild(pills);
    row.appendChild(avatar);
    row.appendChild(stack);
    chatEl.appendChild(row);
    state.lastAiBubble = bubble;
  } else {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.textContent = text;
    chatEl.appendChild(div);
  }
  syncChatEmpty();
  chatEl.scrollTop = chatEl.scrollHeight;
  return state.lastAiBubble;
}

function setSpeakingBubble(on) {
  if (state.lastAiBubble) {
    state.lastAiBubble.classList.toggle("is-speaking-audio", !!on);
  }
}

function setMode(text) {
  const next = text || "";
  modeLine.textContent = next;
  const t = next.toLowerCase();
  const speaking = t.includes("speaking");
  const thinking =
    t.includes("thinking") ||
    t.includes("transcrib") ||
    t.includes("synthesiz") ||
    t.includes("recording");
  document.body.classList.toggle("is-speaking", speaking);
  document.body.classList.toggle("is-thinking", thinking && !speaking);
  if (statusStrip && statusStripText) {
    const active = speaking || thinking;
    statusStrip.hidden = !active;
    statusStrip.dataset.mode = speaking
      ? "speaking"
      : thinking
        ? "thinking"
        : "busy";
    const short = next.includes("·")
      ? next.split("·").pop().trim()
      : next;
    statusStripText.textContent = short || next;
  }
  if (formEl) formEl.classList.toggle("is-busy", !!state.busy);
}

function openSheet(dlg) {
  if (!dlg) return;
  const run = () => {
    if (typeof dlg.showModal === "function" && !dlg.open) dlg.showModal();
  };
  if (document.startViewTransition) {
    document.startViewTransition(run);
  } else {
    run();
  }
}

function closeSheet(dlg) {
  if (!dlg || !dlg.open) return;
  const run = () => dlg.close();
  if (document.startViewTransition) {
    document.startViewTransition(run);
  } else {
    run();
  }
}

function fillSettingsForm() {
  urlInput.value = state.settings.ollamaUrl;
  modelInput.value = state.settings.ollamaModel;
  nameInput.value = state.settings.companionName;
  toneInput.value = state.settings.tone;
  speakInput.checked = !!state.settings.speakReplies;
  if (voiceIdInput) voiceIdInput.value = state.settings.voiceId || "auto";
  if (kokoroVoiceInput)
    kokoroVoiceInput.value =
      state.settings.kokoroVoice || DEFAULTS.kokoroVoice;
  if (voiceEngineInput)
    voiceEngineInput.value = state.settings.voiceEngine || "natural";
  if (voiceTempoInput) {
    voiceTempoInput.value = String(state.settings.voiceTempo || 0);
    if (tempoVal) tempoVal.textContent = voiceTempoInput.value;
  }
  if (voicePitchInput) {
    voicePitchInput.value = String(state.settings.voicePitch || 0);
    if (pitchVal) pitchVal.textContent = voicePitchInput.value;
  }
  if (themeSelect) themeSelect.value = state.settings.theme || "auto";
  settingsStatus.textContent = "";
  settingsStatus.className = "status";
  refreshVoiceLine();
  refreshGoogleLine();
  refreshRemoteAccess();
}

async function refreshRemoteAccess() {
  if (!remoteLine || !remoteUrls) return;
  remoteLine.textContent = "Checking network…";
  remoteUrls.innerHTML = "";
  try {
    const res = await fetch("/api/remote-access");
    const data = await res.json();
    const rows = [];
    for (const url of data.lan_urls || []) {
      rows.push({ label: "Wi‑Fi / LAN", url });
    }
    for (const url of data.tailscale_urls || []) {
      rows.push({ label: "Tailscale (off Wi‑Fi)", url });
    }
    if (!rows.length) {
      remoteLine.textContent =
        data.howto ||
        "No LAN/Tailscale IP found. Install Tailscale for remote access.";
      return;
    }
    remoteLine.textContent = data.tailscale_urls?.length
      ? "Copy a Tailscale URL for mobile data. Keep the PC server running."
      : "On home Wi‑Fi use LAN. For away-from-home, install Tailscale on PC + phone.";
    for (const row of rows) {
      const div = document.createElement("div");
      div.className = "remote-url-row";
      const code = document.createElement("code");
      code.textContent = `${row.label}: ${row.url}`;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ghost";
      btn.textContent = "Copy";
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(row.url);
          btn.textContent = "Copied";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 1200);
        } catch {
          btn.textContent = "Fail";
        }
      });
      div.appendChild(code);
      div.appendChild(btn);
      remoteUrls.appendChild(div);
    }
  } catch (err) {
    remoteLine.textContent = `Remote status unreachable (${err.message})`;
  }
}

async function refreshGoogleLine() {
  if (!googleLine) return;
  try {
    const res = await fetch("/api/google/status");
    const data = await res.json();
    state.google = data;
    if (googleRedirectHint) {
      googleRedirectHint.textContent = `http://127.0.0.1:${window.location.port || "8765"}/api/google/callback`;
    }
    if (!data.configured) {
      googleLine.textContent =
        "Google keys missing — paste Client ID & Secret below, then Sign in.";
      if (googleSetupBox) googleSetupBox.hidden = false;
      if (onboardGoogleSetup) onboardGoogleSetup.hidden = false;
      googleConnectBtn.disabled = false; // will validate on click
      googleConnectBtn.hidden = false;
      googleConnectBtn.textContent = "Sign in with Google";
      googleDisconnectBtn.hidden = true;
      gmailComposeBtn.hidden = true;
      if (googleBanner) {
        showGoogleBanner(true);
        googleBannerTitle.textContent = "Set up Google";
        googleBannerHint.textContent =
          "Paste keys in Settings / onboarding, then Sign in";
        googleBannerBtn.disabled = false;
        googleBannerBtn.textContent = "Open setup";
      }
      if (onboardGoogleStatus) {
        onboardGoogleStatus.className = "status";
        onboardGoogleStatus.textContent =
          "Save Client ID + Secret first (Google Cloud → Web client).";
      }
      return;
    }
    if (googleSetupBox) googleSetupBox.hidden = true;
    if (onboardGoogleSetup) onboardGoogleSetup.hidden = true;
    googleConnectBtn.disabled = false;
    if (googleBannerBtn) googleBannerBtn.disabled = false;
    if (data.connected || data.linked) {
      const who = data.email || data.name || "Google account";
      googleLine.textContent = `Linked as ${who} — Gmail ready`;
      googleConnectBtn.hidden = true;
      googleDisconnectBtn.hidden = false;
      gmailComposeBtn.hidden = false;
      if (driveNoteBtn) driveNoteBtn.hidden = false;
      if (googleBanner) showGoogleBanner(false);
      if (onboardGoogleStatus) {
        onboardGoogleStatus.className = "status ok";
        onboardGoogleStatus.textContent = `Linked as ${who}`;
      }
    } else {
      googleLine.textContent =
        data.flow ||
        "Tap Sign in → Google login → approve → auto-linked.";
      googleConnectBtn.hidden = false;
      googleDisconnectBtn.hidden = true;
      gmailComposeBtn.hidden = true;
      if (googleBanner) {
        showGoogleBanner(true);
        googleBannerTitle.textContent = "Link Google";
        googleBannerHint.textContent =
          "Sign in → approve permissions → auto-linked on this PC";
        googleBannerBtn.textContent = "Sign in with Google";
      }
      if (onboardGoogleStatus) {
        onboardGoogleStatus.className = "status";
        onboardGoogleStatus.textContent = "Keys saved — tap Sign in with Google.";
      }
    }
  } catch (err) {
    googleLine.textContent = `Google status unreachable (${err.message})`;
    googleConnectBtn.disabled = true;
    showGoogleBanner(false);
  }
}

async function saveGoogleCreds(clientId, clientSecret, statusEl) {
  const res = await fetch("/api/google/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  if (statusEl) {
    statusEl.className = "status ok";
    const uris = (data.redirect_uris_hint || []).slice(0, 3).join(" · ");
    statusEl.textContent =
      (data.message || "Saved.") +
      (uris ? ` Allow redirects: ${uris}` : "");
  }
  await refreshGoogleLine();
  return data;
}

async function startGoogleLogin() {
  try {
    const res = await fetch("/api/google/status");
    const data = await res.json();
    if (!data.configured) {
      if (googleSetupBox) googleSetupBox.hidden = false;
      openSettings("connection");
      if (settingsStatus) {
        settingsStatus.className = "status err";
        settingsStatus.textContent =
          "Add Google Client ID + Secret first, Save keys, then Sign in.";
      }
      if (onboardGoogleStatus) {
        onboardGoogleStatus.className = "status err";
        onboardGoogleStatus.textContent =
          "Paste & save Google keys above, then tap Sign in.";
      }
      return;
    }
  } catch (err) {
    addBubble("system", `Google status error: ${err.message}`);
    return;
  }
  // Full-page redirect to Google login + permission consent
  window.location.href = "/api/google/start";
}

function noteGoogleReturn() {
  const params = new URLSearchParams(window.location.search);
  const g = params.get("google");
  if (!g) return;
  if (g === "connected") {
    addBubble(
      "system",
      "Google linked. Your account is connected on this PC — Compose Gmail is in Settings."
    );
  } else if (g === "error") {
    const detail = params.get("detail") || "unknown";
    addBubble("system", `Google sign-in failed: ${detail}`);
  }
  const url = new URL(window.location.href);
  url.searchParams.delete("google");
  url.searchParams.delete("detail");
  window.history.replaceState({}, "", url.pathname + url.hash);
}

async function gmailAction(action) {
  gmailStatus.className = "status";
  gmailStatus.textContent = action === "send" ? "Sending…" : "Saving draft…";
  try {
    const res = await fetch("/api/google/email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        to: gmailTo.value.trim(),
        subject: gmailSubject.value.trim(),
        body: gmailBody.value,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    gmailStatus.className = "status ok";
    gmailStatus.textContent =
      action === "send"
        ? `Sent (${data.message_id || "ok"})`
        : `Draft saved (${data.draft_id || "ok"})`;
  } catch (err) {
    gmailStatus.className = "status err";
    gmailStatus.textContent = String(err.message || err);
  }
}

function systemPrompt() {
  const name = companionLabel();
  const tone = state.settings.tone;
  const hint = TONE_HINTS[tone] || TONE_HINTS.friendly;
  return (
    `You are ${name}, the user's Universal Soul companion — a local-first personal AI. ` +
    `Your name is ${name}. Speak in a ${tone} tone (${hint}). ` +
    "You run privately on their desktop/phone via Ollama, with optional voice, tools, and careful automation. " +
    "Use prior conversation turns for continuity — do not repeat the same greeting or generic offer every time. " +
    "Prefer concise, varied, helpful answers. Do not invent unshipped features."
  );
}

async function loadToolChips() {
  if (!toolChipsEl) return;
  try {
    const res = await fetch("/api/tools");
    const data = await res.json();
    state.tools = data.tools || [];
    toolChipsEl.innerHTML = "";
    const wow = state.tools.filter((t) => t.wow);
    const list = (wow.length ? wow : state.tools).slice(0, 10);
    for (const t of list) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = t.chip || t.title;
      btn.title = t.description || t.title;
      btn.addEventListener("click", () => {
        inputEl.value = t.prompt_hint || `${t.name} `;
        inputEl.focus();
        const len = inputEl.value.length;
        inputEl.setSelectionRange(len, len);
      });
      toolChipsEl.appendChild(btn);
    }
    if (data.search_provider) {
      const tip = document.createElement("button");
      tip.type = "button";
      tip.textContent =
        data.search_provider === "google_cse" ? "Search · Google" : "Search · DDG";
      tip.title = "Web search provider on this PC";
      tip.addEventListener("click", () => {
        inputEl.value = "search ";
        inputEl.focus();
      });
      toolChipsEl.prepend(tip);
    }
  } catch {
    toolChipsEl.innerHTML = "";
  }
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
    if (voiceIdInput && Array.isArray(data.voices) && data.voices.length) {
      const current = voiceIdInput.value || state.settings.voiceId || "auto";
      voiceIdInput.innerHTML = "";
      for (const v of data.voices) {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = v.label || v.id;
        voiceIdInput.appendChild(opt);
      }
      voiceIdInput.value = current;
      if (voiceIdInput.value !== current) voiceIdInput.value = "auto";
    }
    if (
      kokoroVoiceInput &&
      Array.isArray(data.kokoro_voices) &&
      data.kokoro_voices.length
    ) {
      const current =
        kokoroVoiceInput.value ||
        state.settings.kokoroVoice ||
        DEFAULTS.kokoroVoice;
      kokoroVoiceInput.innerHTML = "";
      for (const v of data.kokoro_voices) {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = v.label || v.id;
        kokoroVoiceInput.appendChild(opt);
      }
      kokoroVoiceInput.value = current;
      if (kokoroVoiceInput.value !== current)
        kokoroVoiceInput.value = DEFAULTS.kokoroVoice;
    }
    if (!data.ok) {
      voiceLine.textContent = `Voice PC: unavailable (${data.error || "error"})`;
      return;
    }
    if (data.cloning) {
      voiceLine.textContent = `Voice PC: XTTS clone ready · ${data.clone_wav || "sample set"}`;
    } else if (data.kokoro_available) {
      voiceLine.textContent = `Voice PC: Natural (Kokoro, offline) · ${data.kokoro_voice || "af_heart"}`;
    } else {
      voiceLine.textContent = `Voice PC: Edge neural · ${data.voice_id || "auto"} — upload a sample below for real timbre`;
    }
    if (cloneStatus && data.cloning) {
      cloneStatus.className = "status ok";
      cloneStatus.textContent = "Clone active on PC.";
    }
  } catch (err) {
    voiceLine.textContent = `Voice PC: unreachable (${err.message})`;
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

function pickRecorderMime() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  if (!window.MediaRecorder) return "";
  for (const m of candidates) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

function cloneExtForMime(mime) {
  if ((mime || "").includes("mp4") || (mime || "").includes("m4a")) return ".m4a";
  if ((mime || "").includes("ogg")) return ".ogg";
  return ".webm";
}

async function postCloneAudio(dataUrl, filename) {
  const res = await fetch("/api/voice/clone", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      audio_b64: dataUrl,
      filename: filename || "clone_ref.webm",
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || data.message || `HTTP ${res.status}`);
  }
  return data;
}

async function uploadCloneSample() {
  if (!cloneFile || !cloneFile.files || !cloneFile.files[0]) {
    throw new Error("Choose an audio file first");
  }
  const file = cloneFile.files[0];
  const dataUrl = await fileToBase64(file);
  return postCloneAudio(dataUrl, file.name || "clone_ref.wav");
}

function setCloneRecordUi(recording) {
  if (!cloneRecordBtn) return;
  if (recording) {
    cloneRecordBtn.textContent = "Stop & use";
    cloneRecordBtn.classList.add("recording");
  } else {
    cloneRecordBtn.textContent = "Record voice note";
    cloneRecordBtn.classList.remove("recording");
    if (cloneRecordTimer) cloneRecordTimer.textContent = "";
  }
}

function stopCloneTracks() {
  if (cloneRec.stream) {
    for (const t of cloneRec.stream.getTracks()) t.stop();
  }
  cloneRec.stream = null;
  if (cloneRec.tick) {
    clearInterval(cloneRec.tick);
    cloneRec.tick = null;
  }
}

async function startCloneRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error(
      "Mic not available in this browser. Use HTTPS / localhost, or upload a voice note file."
    );
  }
  if (!window.MediaRecorder) {
    throw new Error("Recording not supported here — upload a voice note file instead.");
  }
  const mime = pickRecorderMime();
  cloneRec.mime = mime || "audio/webm";
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      channelCount: 1,
    },
  });
  cloneRec.stream = stream;
  cloneRec.chunks = [];
  const opts = mime ? { mimeType: mime } : undefined;
  const recorder = opts
    ? new MediaRecorder(stream, opts)
    : new MediaRecorder(stream);
  cloneRec.recorder = recorder;
  cloneRec.startedAt = Date.now();
  recorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) cloneRec.chunks.push(e.data);
  };
  recorder.start(250);
  setCloneRecordUi(true);
  if (cloneRecordTimer) {
    cloneRec.tick = setInterval(() => {
      const sec = Math.floor((Date.now() - cloneRec.startedAt) / 1000);
      cloneRecordTimer.textContent = `${sec}s / 15s`;
      if (sec >= 15) stopCloneRecording(true);
    }, 200);
  }
  if (cloneStatus) {
    cloneStatus.className = "status";
    cloneStatus.textContent =
      "Recording… speak clearly for 6–15 seconds, then tap Stop & use.";
  }
  setMode("Recording voice note…");
}

function stopCloneRecording(auto = false) {
  return new Promise((resolve) => {
    const recorder = cloneRec.recorder;
    if (!recorder || recorder.state === "inactive") {
      stopCloneTracks();
      setCloneRecordUi(false);
      resolve(null);
      return;
    }
    const elapsedMs = Date.now() - cloneRec.startedAt;
    recorder.onstop = async () => {
      stopCloneTracks();
      setCloneRecordUi(false);
      const mime = recorder.mimeType || cloneRec.mime || "audio/webm";
      const blob = new Blob(cloneRec.chunks, { type: mime });
      cloneRec.chunks = [];
      cloneRec.recorder = null;
      if (elapsedMs < 4500) {
        if (cloneStatus) {
          cloneStatus.className = "status err";
          cloneStatus.textContent = auto
            ? "Recording too short — hold at least ~6 seconds."
            : "Too short — speak for at least ~6 seconds, then stop.";
        }
        setMode(`${companionLabel()} · ready`);
        resolve(null);
        return;
      }
      if (clonePreview) {
        const url = URL.createObjectURL(blob);
        if (clonePreview.src) URL.revokeObjectURL(clonePreview.src);
        clonePreview.src = url;
        clonePreview.hidden = false;
      }
      try {
        if (cloneStatus) {
          cloneStatus.className = "status";
          cloneStatus.textContent = "Uploading voice note to PC…";
        }
        const dataUrl = await fileToBase64(blob);
        const ext = cloneExtForMime(mime);
        const data = await postCloneAudio(dataUrl, `clone_voice_note${ext}`);
        if (cloneStatus) {
          cloneStatus.className = "status ok";
          cloneStatus.textContent = data.cloning
            ? `Clone ready from mic: ${data.path || "saved"}`
            : data.tip ||
              data.message ||
              "Voice note saved (Edge until Coqui installed).";
        }
        await refreshVoiceLine();
        setMode(`${companionLabel()} · ready`);
        resolve(data);
      } catch (err) {
        if (cloneStatus) {
          cloneStatus.className = "status err";
          cloneStatus.textContent = String(err.message || err);
        }
        setMode(`${companionLabel()} · ready`);
        resolve(null);
      }
    };
    try {
      recorder.stop();
    } catch {
      stopCloneTracks();
      setCloneRecordUi(false);
      resolve(null);
    }
  });
}

async function toggleCloneRecording() {
  if (cloneRec.recorder && cloneRec.recorder.state === "recording") {
    await stopCloneRecording(false);
    return;
  }
  await startCloneRecording();
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
  // Offline path: LIGHT pack locally + queue for PC sync
  if (!navigator.onLine || state.forceOffline) {
    setOfflineUi(true);
    const reply = localLightReply(message);
    try {
      const q = JSON.parse(localStorage.getItem("usa_offline_queue") || "[]");
      q.push({ text: message, member_id: state.memberId, ts: Date.now() });
      localStorage.setItem("usa_offline_queue", JSON.stringify(q.slice(-50)));
    } catch {
      /* ignore */
    }
    return reply;
  }

  const res = await proxyFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      model: state.settings.ollamaModel,
      ollama_url: state.settings.ollamaUrl,
      companion_name: state.settings.companionName,
      tone: state.settings.tone,
      history: state.history.slice(-12),
      member_id: state.memberId,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    // Fall back to offline light if PC unreachable
    if (String(data.error || "").length || res.status >= 500) {
      setOfflineUi(true);
      await refreshOfflinePack();
      return localLightReply(message);
    }
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  setOfflineUi(false);
  const toolsUsed = [];
  if (data.route && data.route.mode === "deep") {
    toolsUsed.push({
      ok: true,
      tool: "thinkmesh",
      summary: "Deep ThinkMesh route",
    });
  }
  if (Array.isArray(data.tools) && data.tools.length) {
    for (const t of data.tools) {
      if (t.tool === "thinkmesh" && toolsUsed.some((x) => x.tool === "thinkmesh")) {
        continue;
      }
      toolsUsed.push(t);
    }
  }
  const reply = (data.reply || "").trim() || "(empty response)";
  state.lastSpeak = (data.speak || "").trim() || "";
  state.lastTools = toolsUsed;
  return reply;
}

function cleanSpeakText(text) {
  return String(text || "")
    .replace(/https?:\/\/\S+/gi, " ")
    .replace(/<\/?[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function splitSpeakChunks(text, maxLen = 480) {
  const clean = cleanSpeakText(text);
  if (!clean) return [];
  if (clean.length <= maxLen) return [clean];
  const parts = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [clean];
  const chunks = [];
  let cur = "";
  for (const raw of parts) {
    const seg = raw.trim();
    if (!seg) continue;
    const next = cur ? `${cur} ${seg}` : seg;
    if (next.length <= maxLen) {
      cur = next;
      continue;
    }
    if (cur) chunks.push(cur);
    cur = seg.length <= maxLen ? seg : seg.slice(0, maxLen);
  }
  if (cur) chunks.push(cur);
  return chunks.length ? chunks : [clean.slice(0, maxLen)];
}

// Mobile browsers block audio.play() until the user interacts with the page.
// Prime a tiny silent clip on the first gesture so later replies speak on their
// own. Safe to call repeatedly; only the first successful play flips the flag.
const SILENT_WAV =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACIWAAACABAAZGF0YQAAAAA=";

function unlockAudio() {
  if (state.audioUnlocked) return;
  try {
    const a = new Audio(SILENT_WAV);
    a.volume = 0;
    const p = a.play();
    if (p && typeof p.then === "function") {
      p.then(() => {
        state.audioUnlocked = true;
      }).catch(() => {
        /* still locked; will retry on next gesture */
      });
    } else {
      state.audioUnlocked = true;
    }
  } catch {
    /* ignore */
  }
}

function initAudioUnlock() {
  const events = ["pointerdown", "touchstart", "keydown", "click"];
  const handler = () => {
    unlockAudio();
    if (state.audioUnlocked) {
      events.forEach((ev) =>
        document.removeEventListener(ev, handler, { capture: true })
      );
    }
  };
  events.forEach((ev) =>
    document.addEventListener(ev, handler, { capture: true, passive: true })
  );
}

function stopSpeakPlayback() {
  state.speakGen = (state.speakGen || 0) + 1;
  if (state.audio) {
    try {
      state.audio.pause();
      state.audio.src = "";
      URL.revokeObjectURL(state.audio._objUrl || "");
    } catch {
      /* ignore */
    }
    state.audio = null;
  }
  setSpeakingBubble(false);
}

async function speakOneChunk(text, opts = {}) {
  const preview = !!opts.preview;
  const line = cleanSpeakText(text);
  if (!line || /xmlns|www\.w3\.org/i.test(line)) return;
  // Decide the engine. Previews are always fast Edge. For real replies the
  // user's voiceEngine choice applies:
  //  natural   -> Kokoro (offline, natural) — the mobile default
  //  fast      -> Edge neural (online)
  //  authentic -> XTTS clone
  //  auto      -> clone, but a lagging chunk trips state.cloneLagged so the
  //               rest of the reply falls back to fast Edge for responsiveness.
  const choice = state.settings.voiceEngine || "natural";
  let engine = preview ? "fast" : choice;
  if (engine === "auto") {
    engine = state.cloneLagged ? "fast" : "authentic";
  }
  // Natural uses the Kokoro voice catalog; others use the Edge voice id.
  const voiceId =
    engine === "natural"
      ? state.settings.kokoroVoice || DEFAULTS.kokoroVoice
      : state.settings.voiceId || "auto";
  const started = Date.now();
  const res = await fetch("/api/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: line,
      personality: state.settings.tone || "friendly",
      voice_id: voiceId,
      rate_bias: state.settings.voiceTempo || 0,
      pitch_bias: state.settings.voicePitch || 0,
      engine: engine,
      preview: preview,
      max_chars: preview ? 160 : 520,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  // In "auto" mode, if the clone was slow to synthesize this chunk, switch the
  // remainder of the reply to fast Edge so playback keeps up.
  if (choice === "auto" && engine === "authentic" &&
      Date.now() - started > CLONE_LAG_MS) {
    state.cloneLagged = true;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio._objUrl = url;
  state.audio = audio;
  const respEngine = res.headers.get("X-Soul-TTS-Engine") || "tts";
  setMode(`${companionLabel()} · speaking (${respEngine})`);
  setSpeakingBubble(true);
  await new Promise((resolve, reject) => {
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (state.audio === audio) state.audio = null;
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Audio playback failed"));
    };
    audio.play().catch((err) => {
      URL.revokeObjectURL(url);
      if (err && err.name === "NotAllowedError") {
        state.audioUnlocked = false;
        reject(new Error("tap the screen once to enable voice, then resend"));
      } else {
        reject(err);
      }
    });
  });
}

async function speak(text, opts = {}) {
  if (!text || !state.settings.speakReplies) return;
  const preview = !!opts.preview;
  const line = cleanSpeakText(text);
  if (!line || /xmlns|www\.w3\.org/i.test(line)) return;
  // Reset per-reply lag tracking; "auto" mode may set this mid-reply.
  if (!preview) state.cloneLagged = false;
  stopSpeakPlayback();
  const gen = state.speakGen;
  const chunks = splitSpeakChunks(line, preview ? 160 : 480);
  try {
    for (let i = 0; i < chunks.length; i++) {
      if (gen !== state.speakGen) return;
      await speakOneChunk(chunks[i], opts);
    }
    if (gen === state.speakGen) {
      setSpeakingBubble(false);
      setMode(`${companionLabel()} · ready`);
    }
  } catch (err) {
    setSpeakingBubble(false);
    addBubble("system", `Voice error: ${err.message}`);
    setMode(`${companionLabel()} · ready`);
  }
}

function clearChat() {
  state.history = [];
  saveHistory(state.history);
  chatEl.querySelectorAll(".bubble-row, .bubble").forEach((n) => n.remove());
  state.lastAiBubble = null;
  syncChatEmpty();
  addBubble("system", `Chat cleared. ${companionLabel()} is listening fresh.`);
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message || state.busy) return;
  state.busy = true;
  sendBtn.disabled = true;
  inputEl.disabled = true;
  if (chatMicBtn) chatMicBtn.disabled = true;
  if (chatNoteBtn) chatNoteBtn.disabled = true;
  if (formEl) formEl.classList.add("is-busy");
  inputEl.value = "";
  addBubble("user", message);
  setMode("Thinking…");
  try {
    const reply = await chat(message);
    state.history.push({ role: "user", text: message });
    state.history.push({ role: "assistant", text: reply });
    saveHistory(state.history);
    addBubble("ai", reply, { tools: state.lastTools || [] });
    setMode(`${companionLabel()} · ready`);
    const line = (state.lastSpeak || reply || "").trim();
    if (line) await speak(line);
  } catch (err) {
    addBubble("system", `Ollama error: ${err.message}`);
    setMode("Offline / demo");
  } finally {
    state.busy = false;
    sendBtn.disabled = false;
    inputEl.disabled = false;
    if (chatMicBtn) chatMicBtn.disabled = false;
    if (chatNoteBtn) chatNoteBtn.disabled = false;
    if (formEl) formEl.classList.remove("is-busy");
    inputEl.focus();
  }
});

async function sendChatMessage(message) {
  const text = (message || "").trim();
  if (!text || state.busy) return;
  inputEl.value = text;
  formEl.requestSubmit();
}

const chatMic = {
  recording: false,
  recognition: null,
  recorder: null,
  stream: null,
  chunks: [],
  mime: "audio/webm",
};

function micBlockedHelp(errMsg) {
  const host = location.hostname || "";
  const isLocal =
    host === "127.0.0.1" || host === "localhost" || host === "[::1]";
  const insecure = !window.isSecureContext;
  if (/not-allowed|permission|denied|security/i.test(errMsg) || insecure) {
    if (insecure && !isLocal) {
      return (
        "Mic blocked on plain HTTP LAN. On the phone tap Note to attach a saved voice memo, " +
        "or type. Live Mic works on the PC at http://127.0.0.1:8765/."
      );
    }
    return (
      "Microphone permission denied. Allow mic for this site, or tap Note to attach a voice memo."
    );
  }
  return errMsg || "Voice note failed";
}

async function transcribeBlob(blob, filename) {
  setMode("Transcribing on PC…");
  const dataUrl = await fileToBase64(blob);
  const res = await fetch("/api/transcribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      audio_b64: dataUrl,
      filename: filename || "chat_voice_note.webm",
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return (data.text || "").trim();
}

function stopChatMicTracks() {
  if (chatMic.stream) {
    for (const t of chatMic.stream.getTracks()) t.stop();
  }
  chatMic.stream = null;
  if (chatMicBtn) chatMicBtn.classList.remove("recording");
  chatMic.recording = false;
}

function browserSpeechAvailable() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

async function startBrowserSpeech() {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Rec();
  chatMic.recognition = rec;
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  return new Promise((resolve, reject) => {
    let finalText = "";
    rec.onresult = (ev) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += t;
        else interim += t;
      }
      inputEl.value = (finalText || interim).trim();
    };
    rec.onerror = (ev) => {
      stopChatMicTracks();
      reject(new Error(ev.error || "Speech recognition failed"));
    };
    rec.onend = () => {
      stopChatMicTracks();
      resolve((finalText || inputEl.value || "").trim());
    };
    chatMic.recording = true;
    if (chatMicBtn) chatMicBtn.classList.add("recording");
    setMode("Listening… tap Mic again to stop");
    try {
      rec.start();
    } catch (err) {
      stopChatMicTracks();
      reject(err);
    }
  });
}

function stopBrowserSpeech() {
  try {
    if (chatMic.recognition) chatMic.recognition.stop();
  } catch {
    /* ignore */
  }
}

async function recordChatNoteToPc() {
  if (
    !window.isSecureContext &&
    location.hostname !== "127.0.0.1" &&
    location.hostname !== "localhost"
  ) {
    throw new Error("not-allowed");
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    throw new Error("Mic recording not supported — tap Note or type instead.");
  }
  const mime = pickRecorderMime();
  chatMic.mime = mime || "audio/webm";
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
  } catch (err) {
    throw new Error(
      err && err.name === "NotAllowedError"
        ? "not-allowed"
        : String(err.message || err)
    );
  }
  chatMic.stream = stream;
  chatMic.chunks = [];
  const recorder = mime
    ? new MediaRecorder(stream, { mimeType: mime })
    : new MediaRecorder(stream);
  chatMic.recorder = recorder;
  recorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) chatMic.chunks.push(e.data);
  };
  const done = new Promise((resolve, reject) => {
    recorder.onstop = async () => {
      stopChatMicTracks();
      try {
        const blob = new Blob(chatMic.chunks, {
          type: recorder.mimeType || chatMic.mime,
        });
        chatMic.chunks = [];
        chatMic.recorder = null;
        if (blob.size < 1200) {
          reject(
            new Error("Voice note too short — hold Mic and speak longer.")
          );
          return;
        }
        const ext = cloneExtForMime(recorder.mimeType || chatMic.mime);
        resolve(await transcribeBlob(blob, `chat_voice_note${ext}`));
      } catch (err) {
        reject(err);
      }
    };
  });
  recorder.start(250);
  chatMic.recording = true;
  if (chatMicBtn) chatMicBtn.classList.add("recording");
  setMode("Recording… tap Mic to send");
  setTimeout(() => {
    if (chatMic.recorder && chatMic.recorder.state === "recording") {
      try {
        chatMic.recorder.stop();
      } catch {
        /* ignore */
      }
    }
  }, 45000);
  return done;
}

function stopChatNoteRecord() {
  if (chatMic.recorder && chatMic.recorder.state === "recording") {
    chatMic.recorder.stop();
    return true;
  }
  return false;
}

async function toggleChatMic() {
  if (state.busy) return;
  if (chatMic.recording) {
    if (chatMic.recognition) stopBrowserSpeech();
    else stopChatNoteRecord();
    return;
  }
  if (
    !window.isSecureContext &&
    location.hostname !== "127.0.0.1" &&
    location.hostname !== "localhost"
  ) {
    addBubble(
      "system",
      "Live Mic is blocked on http://LAN by the browser. Tap Note to attach a voice memo, or type."
    );
    if (chatNoteFile) chatNoteFile.click();
    return;
  }
  try {
    let text = "";
    if (browserSpeechAvailable()) {
      text = await startBrowserSpeech();
    } else {
      text = await recordChatNoteToPc();
    }
    if (!text) {
      setMode(`${companionLabel()} · ready`);
      addBubble("system", "No speech heard — try again, or tap Note.");
      return;
    }
    inputEl.value = text;
    await sendChatMessage(text);
  } catch (err) {
    stopChatMicTracks();
    const msg = String(err.message || err);
    if (/not-allowed|permission|denied/i.test(msg)) {
      addBubble("system", micBlockedHelp(msg));
      if (chatNoteFile) chatNoteFile.click();
      setMode(`${companionLabel()} · ready`);
      return;
    }
    if (browserSpeechAvailable() && !/too short/i.test(msg)) {
      try {
        setMode("Trying PC transcription…");
        const text = await recordChatNoteToPc();
        if (text) {
          inputEl.value = text;
          await sendChatMessage(text);
          return;
        }
      } catch (err2) {
        addBubble("system", micBlockedHelp(String(err2.message || err2)));
        if (chatNoteFile) chatNoteFile.click();
        setMode(`${companionLabel()} · ready`);
        return;
      }
    }
    addBubble("system", micBlockedHelp(msg));
    setMode(`${companionLabel()} · ready`);
  }
}

async function uploadChatVoiceMemo(file) {
  if (!file) return;
  try {
    setMode("Transcribing voice memo…");
    const text = await transcribeBlob(file, file.name || "voice_memo.m4a");
    if (!text) {
      addBubble("system", "Could not understand that memo — try again.");
      setMode(`${companionLabel()} · ready`);
      return;
    }
    inputEl.value = text;
    await sendChatMessage(text);
  } catch (err) {
    addBubble("system", `Voice memo error: ${err.message || err}`);
    setMode(`${companionLabel()} · ready`);
  }
}

if (chatMicBtn) {
  chatMicBtn.addEventListener("click", () => {
    toggleChatMic();
  });
}

if (chatNoteBtn && chatNoteFile) {
  chatNoteBtn.addEventListener("click", () => chatNoteFile.click());
  chatNoteFile.addEventListener("change", async () => {
    const file = chatNoteFile.files && chatNoteFile.files[0];
    chatNoteFile.value = "";
    if (file) await uploadChatVoiceMemo(file);
  });
}

if (menuBtn) {
  menuBtn.addEventListener("click", () => openMenuSheet());
}
if (menuCloseBtn && menuDialog) {
  menuCloseBtn.addEventListener("click", () => closeSheet(menuDialog));
}
if (menuSettingsBtn) {
  menuSettingsBtn.addEventListener("click", () => {
    closeSheet(menuDialog);
    openSettings("companion");
  });
}
if (menuFamilyBtn) {
  menuFamilyBtn.addEventListener("click", async () => {
    closeSheet(menuDialog);
    await refreshFamily();
    openSheet(familyDialog);
  });
}
if (menuInviteBtn) {
  menuInviteBtn.addEventListener("click", async () => {
    closeSheet(menuDialog);
    openSheet(familyDialog);
    await refreshFamily();
    if (familyQrBox) familyQrBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
}
if (settingsFamilyBtn) {
  settingsFamilyBtn.addEventListener("click", async () => {
    closeSheet(dialog);
    await refreshFamily();
    openSheet(familyDialog);
  });
}
if (googleBannerDismiss) {
  googleBannerDismiss.addEventListener("click", () => {
    localStorage.setItem(GOOGLE_BANNER_KEY, "1");
    showGoogleBanner(false);
  });
}

if (themeSelect) {
  themeSelect.addEventListener("change", () => applyTheme(themeSelect.value));
}

if (voiceTempoInput) {
  voiceTempoInput.addEventListener("input", () => {
    if (tempoVal) tempoVal.textContent = voiceTempoInput.value;
  });
}
if (voicePitchInput) {
  voicePitchInput.addEventListener("input", () => {
    if (pitchVal) pitchVal.textContent = voicePitchInput.value;
  });
}

if (cloneUploadBtn) {
  cloneUploadBtn.addEventListener("click", async () => {
    if (!cloneStatus) return;
    cloneStatus.className = "status";
    cloneStatus.textContent = "Uploading sample to PC…";
    try {
      const data = await uploadCloneSample();
      cloneStatus.className = "status ok";
      cloneStatus.textContent = data.cloning
        ? `Clone ready: ${data.path || "saved"}`
        : data.tip || data.message || "Sample saved (Edge until Coqui installed).";
      await refreshVoiceLine();
    } catch (err) {
      cloneStatus.className = "status err";
      cloneStatus.textContent = String(err.message || err);
    }
  });
}

if (cloneRecordBtn) {
  cloneRecordBtn.addEventListener("click", async () => {
    try {
      await toggleCloneRecording();
    } catch (err) {
      stopCloneTracks();
      setCloneRecordUi(false);
      if (cloneStatus) {
        cloneStatus.className = "status err";
        cloneStatus.textContent = String(err.message || err);
      }
    }
  });
}

if (cloneDemoBtn) {
  cloneDemoBtn.addEventListener("click", async () => {
    if (!cloneStatus) return;
    cloneStatus.className = "status";
    cloneStatus.textContent = "Building demo sample on PC…";
    try {
      const res = await fetch("/api/voice/clone/demo", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        throw new Error(data.error || data.message || `HTTP ${res.status}`);
      }
      cloneStatus.className = "status ok";
      cloneStatus.textContent = data.message || "Demo sample set.";
      await refreshVoiceLine();
    } catch (err) {
      cloneStatus.className = "status err";
      cloneStatus.textContent = String(err.message || err);
    }
  });
}

if (cloneClearBtn) {
  cloneClearBtn.addEventListener("click", async () => {
    if (!cloneStatus) return;
    cloneStatus.className = "status";
    cloneStatus.textContent = "Clearing…";
    try {
      const res = await fetch("/api/voice/clone/clear", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        throw new Error(data.error || data.message || `HTTP ${res.status}`);
      }
      if (cloneFile) cloneFile.value = "";
      cloneStatus.className = "status ok";
      cloneStatus.textContent = data.message || "Clone cleared.";
      await refreshVoiceLine();
    } catch (err) {
      cloneStatus.className = "status err";
      cloneStatus.textContent = String(err.message || err);
    }
  });
}

if (remoteRefreshBtn) {
  remoteRefreshBtn.addEventListener("click", () => refreshRemoteAccess());
}

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
  state.settings.voiceId = voiceIdInput ? voiceIdInput.value : state.settings.voiceId;
  state.settings.kokoroVoice = kokoroVoiceInput
    ? kokoroVoiceInput.value
    : state.settings.kokoroVoice;
  state.settings.voiceEngine = voiceEngineInput
    ? voiceEngineInput.value
    : state.settings.voiceEngine;
  state.settings.voiceTempo = voiceTempoInput
    ? Number(voiceTempoInput.value)
    : state.settings.voiceTempo;
  state.settings.voicePitch = voicePitchInput
    ? Number(voicePitchInput.value)
    : state.settings.voicePitch;
  applyBrand();
  settingsStatus.className = "status";
  settingsStatus.textContent = "Synthesizing on PC…";
  try {
    await speak(`Hi, I'm ${companionLabel()}. This is my ${state.settings.tone} voice.`, {
      preview: true,
    });
    settingsStatus.className = "status ok";
    settingsStatus.textContent = "Voice preview played (Edge, short clip).";
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

googleConnectBtn.addEventListener("click", () => {
  startGoogleLogin();
});

if (googleBannerBtn) {
  googleBannerBtn.addEventListener("click", async () => {
    if (state.google && !state.google.configured) {
      openSettings("connection");
      return;
    }
    if (!googleBannerBtn.disabled) startGoogleLogin();
  });
}

if (googleSaveCredsBtn) {
  googleSaveCredsBtn.addEventListener("click", async () => {
    googleSetupStatus.className = "status";
    googleSetupStatus.textContent = "Saving…";
    try {
      await saveGoogleCreds(
        googleClientId.value,
        googleClientSecret.value,
        googleSetupStatus
      );
      googleClientSecret.value = "";
    } catch (err) {
      googleSetupStatus.className = "status err";
      googleSetupStatus.textContent = String(err.message || err);
    }
  });
}

if (onboardSaveCreds) {
  onboardSaveCreds.addEventListener("click", async () => {
    onboardGoogleStatus.className = "status";
    onboardGoogleStatus.textContent = "Saving…";
    try {
      await saveGoogleCreds(
        onboardClientId.value,
        onboardClientSecret.value,
        onboardGoogleStatus
      );
      onboardClientSecret.value = "";
    } catch (err) {
      onboardGoogleStatus.className = "status err";
      onboardGoogleStatus.textContent = String(err.message || err);
    }
  });
}

googleDisconnectBtn.addEventListener("click", async () => {
  settingsStatus.className = "status";
  settingsStatus.textContent = "Disconnecting…";
  try {
    await fetch("/api/google/disconnect", { method: "POST" });
    await refreshGoogleLine();
    settingsStatus.className = "status ok";
    settingsStatus.textContent = "Google disconnected on this PC.";
  } catch (err) {
    settingsStatus.className = "status err";
    settingsStatus.textContent = String(err.message || err);
  }
});

gmailComposeBtn.addEventListener("click", () => {
  gmailStatus.textContent = "";
  gmailStatus.className = "status";
  openSheet(gmailDialog);
});

if (driveNoteBtn) {
  driveNoteBtn.addEventListener("click", async () => {
    const text = prompt("Note to save on Google Drive:");
    if (text == null || !String(text).trim()) return;
    const title = prompt("File title:", "Soul note") || "Soul note";
    try {
      const res = await fetch("/api/google/drive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save", title, body: text }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Drive save failed");
      settingsStatus.className = "status ok";
      settingsStatus.textContent = `Saved to Drive: ${data.name || data.file_id}`;
      addBubble("system", `Drive note saved: ${data.web_link || data.name}`);
    } catch (err) {
      settingsStatus.className = "status err";
      settingsStatus.textContent = String(err.message || err);
    }
  });
}

gmailDraftBtn.addEventListener("click", () => gmailAction("draft"));
gmailSendBtn.addEventListener("click", () => {
  if (!confirm("Send this email with your Google account?")) return;
  gmailAction("send");
});

gmailForm.addEventListener("submit", (e) => {
  const submitter = e.submitter;
  if (submitter && submitter.value === "cancel") return;
  e.preventDefault();
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
    voiceId: voiceIdInput ? voiceIdInput.value : "auto",
    kokoroVoice: kokoroVoiceInput
      ? kokoroVoiceInput.value
      : DEFAULTS.kokoroVoice,
    voiceEngine: voiceEngineInput ? voiceEngineInput.value : "natural",
    voiceTempo: voiceTempoInput ? voiceTempoInput.value : 0,
    voicePitch: voicePitchInput ? voicePitchInput.value : 0,
    theme: themeSelect ? themeSelect.value : "auto",
  });
  applyTheme(state.settings.theme);
  localStorage.setItem(STORAGE_KEY + ":tone_set", "1");
  applyBrand();
  pushProfileToPc();
  settingsStatus.className = "status ok";
  settingsStatus.textContent = "Saved locally + synced to PC profile.";
  setMode(`${companionLabel()} · saved`);
  closeSheet(dialog);
});

if (memberSelect) {
  memberSelect.addEventListener("change", async () => {
    const mid = memberSelect.value || "primary";
    const member = (state.family && state.family.members || []).find(
      (m) => m.id === mid
    );
    if (member && member.has_pin) {
      const pin = prompt(`PIN for ${member.display_name || mid}`) || "";
      try {
        const res = await fetch("/api/family/auth", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ member_id: mid, pin }),
        });
        const data = await res.json();
        if (!data.ok) {
          addBubble("system", data.error || "PIN rejected");
          memberSelect.value = state.memberId;
          return;
        }
      } catch (err) {
        addBubble("system", String(err.message || err));
        memberSelect.value = state.memberId;
        return;
      }
    }
    state.memberId = mid;
    localStorage.setItem("usa_member_id", mid);
    await syncSharedHistory();
    addBubble("system", `Switched to ${memberSelect.selectedOptions[0].textContent}`);
  });
}

function csvList(raw) {
  return String(raw || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

if (familySaveBtn) {
  familySaveBtn.addEventListener("click", async () => {
    familyStatus.textContent = "Saving…";
    try {
      const res = await fetch("/api/family", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: familyEnabled.checked,
          name: householdName.value,
          shared_values: csvList(familyValues.value),
          boundaries: csvList(familyBoundaries.value),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "save failed");
      familyStatus.className = "status ok";
      familyStatus.textContent = "Family context saved on PC.";
      await refreshFamily();
    } catch (err) {
      familyStatus.className = "status err";
      familyStatus.textContent = String(err.message || err);
    }
  });
}

if (memberAddBtn) {
  memberAddBtn.addEventListener("click", async () => {
    familyStatus.textContent = "Saving member…";
    try {
      const res = await fetch("/api/family/member", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: memberName.value,
          role: memberRole.value,
          pin: memberPin.value,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "member failed");
      familyStatus.className = "status ok";
      familyStatus.textContent = `Member saved (${data.member_id}).`;
      memberName.value = "";
      memberPin.value = "";
      await refreshFamily();
    } catch (err) {
      familyStatus.className = "status err";
      familyStatus.textContent = String(err.message || err);
    }
  });
}

if (boardAddBtn) {
  boardAddBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/family/board", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: boardFact.value,
          member_id: state.memberId,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "board failed");
      boardFact.value = "";
      familyStatus.className = "status ok";
      familyStatus.textContent = "Board fact added.";
    } catch (err) {
      familyStatus.className = "status err";
      familyStatus.textContent = String(err.message || err);
    }
  });
}

if (reminderAddBtn) {
  reminderAddBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/family/reminder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: reminderText.value,
          member_id: state.memberId,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "reminder failed");
      reminderText.value = "";
      familyStatus.className = "status ok";
      familyStatus.textContent = "Reminder added.";
      await refreshReminders();
    } catch (err) {
      familyStatus.className = "status err";
      familyStatus.textContent = String(err.message || err);
    }
  });
}

window.addEventListener("online", async () => {
  state.forceOffline = false;
  try {
    // Drain any queued offline messages first
    const q = JSON.parse(localStorage.getItem("usa_offline_queue") || "[]");
    for (const item of q) {
      await fetch("/api/offline/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item),
      });
    }
    localStorage.removeItem("usa_offline_queue");
    await fetch("/api/offline/drain", { method: "POST" });
    await refreshOfflinePack();
    await probe();
    setOfflineUi(false);
    setMode(`${companionLabel()} · ready`);
    addBubble(
      "system",
      "Back online — PC brain reachable again. Offline queue synced."
    );
  } catch {
    // Network says online but PC/LAN not ready yet — stay degraded, retry soon
    setOfflineUi(true);
    setMode(`${companionLabel()} · reconnecting…`);
    setTimeout(async () => {
      try {
        await probe();
        setOfflineUi(false);
        setMode(`${companionLabel()} · ready`);
        addBubble("system", "Reconnected to PC brain.");
      } catch {
        /* still waiting for Wi‑Fi / server */
      }
    }, 2500);
  }
});
window.addEventListener("offline", () => {
  setOfflineUi(true);
  setMode(`${companionLabel()} · offline light`);
});

async function createInvite(role, hint, target) {
  const res = await fetch("/api/family/invite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      role: role || "sibling",
      display_name: hint || "",
      created_by: state.memberId || "primary",
    }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "invite failed");
  lastInviteUrl = data.join_url || "";
  if (target === "onboard") {
    onboardQrBox.hidden = false;
    onboardQrImg.src = data.qr_url;
    onboardInviteUrl.textContent = data.join_url;
  } else {
    familyQrBox.hidden = false;
    familyQrImg.src = data.qr_url;
    familyInviteUrl.textContent = data.join_url;
  }
  return data;
}

function showOnboardStep(step) {
  onboardStep = step;
  const panes = [
    onboardPaneWelcome,
    onboardPaneName,
    onboardPaneGoogle,
    onboardPaneInvite,
  ];
  const titles = [
    "Welcome to Universal Soul",
    "Name your companion",
    "Link Google",
    "Invite siblings / staff",
  ];
  const hints = [
    "Phone client ↔ PC brain. One household, shared memory.",
    "This is how they greet you on every device.",
    "Optional: sign in and approve permissions so mail can auto-link.",
    "Generate a QR. They scan it on Wi‑Fi to link their device.",
  ];
  panes.forEach((p, i) => {
    if (p) p.hidden = i !== step;
  });
  onboardStepLabel.textContent = `Step ${step + 1} of 4`;
  onboardTitle.textContent = titles[step];
  onboardHint.textContent = hints[step];
  onboardBack.hidden = step === 0;
  onboardNext.textContent = step === 3 ? "Finish" : "Continue";
}

async function finishOnboarding() {
  localStorage.setItem(ONBOARD_KEY, "1");
  if (onboard) onboard.hidden = true;
  await refreshFamily();
  addBubble(
    "system",
    "Onboarding complete. Use Invite anytime for a sibling/staff QR link."
  );
}

async function runOnboardNext() {
  if (onboardStep === 1) {
    const name = (onboardName.value || "").trim() || state.settings.companionName;
    const tone = onboardTone.value || state.settings.tone;
    state.settings = saveSettings({
      ...state.settings,
      companionName: name,
      tone,
    });
    applyBrand();
    await pushProfileToPc();
    await fetch("/api/family", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: true,
        name: (onboardHouse.value || "Our household").trim(),
      }),
    });
  }
  if (onboardStep >= 3) {
    await finishOnboarding();
    return;
  }
  showOnboardStep(onboardStep + 1);
}

function maybeStartOnboarding() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("invite")) return; // join flow instead
  if (params.get("google") === "connected") {
    localStorage.setItem(ONBOARD_KEY + ":google", "1");
  }
  if (localStorage.getItem(ONBOARD_KEY)) return;
  if (!onboard) return;
  onboard.hidden = false;
  onboardName.value = state.settings.companionName || "";
  onboardTone.value = state.settings.tone || "friendly";
  showOnboardStep(0);
}

async function openJoinFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("invite");
  if (!token || !joinInvite) return false;
  pendingInviteToken = token;
  try {
    const res = await fetch(`/api/family/invite?token=${encodeURIComponent(token)}`);
    const data = await res.json();
    if (!data.ok) {
      joinHint.textContent = data.error || "Invite invalid";
    } else {
      joinHint.textContent = `Join “${data.household || "household"}” as ${data.role || "member"}.`;
      if (data.display_name_hint) joinName.value = data.display_name_hint;
    }
  } catch (err) {
    joinHint.textContent = String(err.message || err);
  }
  joinInvite.hidden = false;
  if (onboard) onboard.hidden = true;
  return true;
}

if (onboardNext) {
  onboardNext.addEventListener("click", () => runOnboardNext());
}
if (onboardBack) {
  onboardBack.addEventListener("click", () => {
    if (onboardStep > 0) showOnboardStep(onboardStep - 1);
  });
}
if (onboardGoogleBtn) {
  onboardGoogleBtn.addEventListener("click", () => {
    localStorage.setItem(ONBOARD_KEY + ":pending_google", "1");
    startGoogleLogin();
  });
}
if (onboardGoogleSkip) {
  onboardGoogleSkip.addEventListener("click", () => showOnboardStep(3));
}
if (onboardMakeInvite) {
  onboardMakeInvite.addEventListener("click", async () => {
    try {
      await createInvite(onboardInviteRole.value, onboardInviteHint.value, "onboard");
    } catch (err) {
      addBubble("system", `Invite error: ${err.message}`);
    }
  });
}
if (onboardCopyInvite) {
  onboardCopyInvite.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(onboardInviteUrl.textContent || "");
      onboardCopyInvite.textContent = "Copied";
    } catch {
      onboardCopyInvite.textContent = "Copy failed";
    }
  });
}
if (onboardWhatsApp) {
  onboardWhatsApp.addEventListener("click", () => {
    openWhatsAppShare(onboardInviteUrl.textContent || lastInviteUrl);
  });
}
if (onboardShare) {
  onboardShare.addEventListener("click", async () => {
    const result = await nativeShareInvite(
      onboardInviteUrl.textContent || lastInviteUrl
    );
    if (result === "copied") onboardShare.textContent = "Link copied";
  });
}
if (familyCopyInvite) {
  familyCopyInvite.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(familyInviteUrl.textContent || "");
      familyCopyInvite.textContent = "Copied";
    } catch {
      familyCopyInvite.textContent = "Copy failed";
    }
  });
}
if (familyWhatsApp) {
  familyWhatsApp.addEventListener("click", () => {
    openWhatsAppShare(familyInviteUrl.textContent || lastInviteUrl);
  });
}
if (familyShare) {
  familyShare.addEventListener("click", async () => {
    const result = await nativeShareInvite(
      familyInviteUrl.textContent || lastInviteUrl
    );
    if (result === "copied") familyShare.textContent = "Link copied";
  });
}
if (familyInviteBtn) {
  familyInviteBtn.addEventListener("click", async () => {
    familyStatus.textContent = "Creating invite…";
    try {
      await createInvite(familyInviteRole.value, "", "family");
      familyStatus.className = "status ok";
      familyStatus.textContent = "QR ready — sibling/staff scan on same Wi‑Fi.";
    } catch (err) {
      familyStatus.className = "status err";
      familyStatus.textContent = String(err.message || err);
    }
  });
}
if (joinSubmit) {
  joinSubmit.addEventListener("click", async () => {
    joinStatus.textContent = "Linking…";
    try {
      const res = await fetch("/api/family/invite/redeem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: pendingInviteToken,
          display_name: joinName.value.trim(),
          pin: joinPin.value,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "join failed");
      state.memberId = data.member_id;
      localStorage.setItem("usa_member_id", data.member_id);
      localStorage.setItem(ONBOARD_KEY, "1");
      joinInvite.hidden = true;
      const url = new URL(window.location.href);
      url.searchParams.delete("invite");
      window.history.replaceState({}, "", url.pathname + url.hash);
      await refreshFamily();
      addBubble("system", data.message || "Device linked to household.");
    } catch (err) {
      joinStatus.className = "status err";
      joinStatus.textContent = String(err.message || err);
    }
  });
}
if (joinCancel) {
  joinCancel.addEventListener("click", () => {
    joinInvite.hidden = true;
    const url = new URL(window.location.href);
    url.searchParams.delete("invite");
    window.history.replaceState({}, "", url.pathname + url.hash);
  });
}

async function boot() {
  applyTheme(state.settings.theme);
  initAudioUnlock();
  initSettingsTabs();
  initStarterChips();
  applyBrand();
  noteGoogleReturn();
  const joining = await openJoinFromUrl();
  await syncProfileFromPc();
  applyBrand();
  if (!joining) maybeStartOnboarding();
  // Resume onboarding after Google OAuth return
  if (
    localStorage.getItem(ONBOARD_KEY + ":pending_google") &&
    !localStorage.getItem(ONBOARD_KEY)
  ) {
    localStorage.removeItem(ONBOARD_KEY + ":pending_google");
    if (onboard) {
      onboard.hidden = false;
      showOnboardStep(3);
      if (onboardGoogleStatus) {
        onboardGoogleStatus.className = "status ok";
        onboardGoogleStatus.textContent = "Google linked (or skipped if not configured).";
      }
    }
  }
  setMode(`${companionLabel()} · checking`);
  await refreshVoiceLine();
  await refreshGoogleLine();
  await loadToolChips();
  await refreshFamily();
  await refreshOfflinePack();
  await syncSharedHistory();
  setOfflineUi(!navigator.onLine);
  syncChatEmpty();
  try {
    await probe();
    setMode(`${companionLabel()} · ready`);
    if (state.history.length) {
      addBubble(
        "system",
        `Shared memory: ${state.history.length} recent turns. Continue anytime.`
      );
    }
    // Fresh chat keeps the empty hero ("Say hello…") until the first message.
  } catch (err) {
    setOfflineUi(true);
    setMode("Offline light / open Settings");
    addBubble(
      "system",
      `PC brain unreachable (${err.message}). Limited offline replies until LAN + Ollama are up.`
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
