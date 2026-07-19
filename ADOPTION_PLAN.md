# Adoption Plan: Integrating Features from TwoSoul & Universal-Soul-AI

**Date:** July 16, 2026  
**Target Project:** Universal-AI-Soul-Unlimited  
**Source Projects:**
- TwoSoul-Mobile-AI-Assistant
- universal-soul-ai (SynergyCore™)

---

## Executive Summary

This document outlines a strategic plan to adopt the best features from TwoSoul and universal-soul-ai into Universal-AI-Soul-Unlimited, creating a unified, best-in-class AI companion system.

### Current State
- **Universal-AI-Soul-Unlimited**: ~50-58% complete, functional desktop + Android shell, PWA client
- **TwoSoul**: Early stage (2 commits), performance benchmarking focus, minimal implementation
- **universal-soul-ai**: Production-ready enterprise platform with extensive features

### Adoption Strategy: **3-Phase Enhancement**

---

## Phase 1: Performance & Benchmarking Infrastructure (TwoSoul)

### 1.1 Benchmarking Suite ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (6/6 unit tests pass).

**What shipped (differs from original stub below):** The project already had a
strong **accuracy** suite (`benchmarks/`: MMLU, HellaSwag, ARC, TruthfulQA,
GSM8K). The real gap TwoSoul filled was **system performance**. TwoSoul's own
`benchmark_suite.py` was almost entirely *simulated* (np.random / time.sleep /
hardcoded accuracy), so instead of copying it we adopted only its reusable idea
(psutil `PerformanceMonitor`) and built a **real** measurement suite:

- `benchmarks/system_performance_benchmark.py` — `PerformanceMonitor` +
  `SystemPerformanceBenchmark`: latency p50/p95/p99, throughput, peak memory,
  avg CPU, error counts — all measured from **actual** inference calls.
- `benchmarks/run_system_performance.py` — runner (auto-detects local models +
  running Ollama), writes JSON to `benchmark_results/`.
- `benchmarks/test_system_performance.py` — 6 pytest tests.
- Hooked into `run_comprehensive_benchmarks.py` so every model gets a perf
  measurement alongside accuracy in one run.

**Validated:** ran live against 11 detected Ollama models; timeouts on heavy
models were caught/counted (no crash). Dummy path + JSON serialization verified.

**Original plan (superseded by the above):**

**Adopt from:** `TwoSoul-Mobile-AI-Assistant/benchmark/`

**What to integrate:**
```python
# New: Universal-AI-Soul-Unlimited/benchmarks/
├── benchmark_suite.py       # Comprehensive performance testing
├── performance_monitor.py   # Real-time metrics
├── mlperf_mobile.py        # Industry-standard benchmarks
├── ai_benchmark.py         # AI Benchmark suite
└── reports/                # Benchmark results & tracking
```

**Benefits:**
- Measure current performance scientifically
- Track optimization improvements over time
- Compare against industry standards (MLPerf, AnTuTu AI)
- Validate optimization claims

**Implementation Priority:** HIGH (Week 1-2)

**Integration Points:**
- Hook into existing `thinkmesh_core/monitoring/performance_tracker.py`
- Add benchmarking to CI/CD pipeline
- Create dashboard for results tracking

---

### 1.2 Advanced Optimization Engine ⭐ HIGH VALUE

#### 1.2a Runtime Optimizer ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (8/8 unit tests pass; verified live on a
32-thread / 11 GB-VRAM machine — correctly selected the "capable" tier and
degraded GPU→CPU under a simulated HOT thermal state).

**Honest scope correction:** TwoSoul's `optimization_engine.py` targets
*training-time* PyTorch model surgery (INT8 quantization, magnitude pruning,
knowledge distillation). This project runs **pre-quantized GGUF models via the
Ollama HTTP API** — the weights are already quantized at download time and there
is no training loop, labeled dataset, or in-process PyTorch model to prune or
re-quantize. Adopting that engine verbatim would produce misleading claims
(75% size reduction / 3× speedup are not achievable by re-quantizing an
already-quantized GGUF at runtime). Also note TwoSoul ships **no thermal code**
at all despite the `thermal_manager.py` line above.

**What shipped instead — the genuinely feasible, real deliverable:**

- `thinkmesh_core/localai/runtime_optimizer.py` (NEW) — `RuntimeOptimizer` with:
  - **Hardware detection** (real): RAM/threads via psutil, VRAM via nvidia-smi,
    graceful CPU fallback.
  - **Hardware-aware runtime parameters**: scales `num_ctx` / `num_gpu` /
    `num_thread` (the knobs Ollama actually respects) to measured memory.
  - **Thermal-aware degradation**: `ThermalState` NORMAL/WARM/HOT reduces context
    and offloads to CPU to cut power draw when hot.
  - **Device model-tier profiles**: light / fast / capable, auto-selected by RAM.
- Exported from `thinkmesh_core/localai/__init__.py`.
- `tests/test_runtime_optimizer.py` — 8 deterministic tests (+ a real-detection
  smoke test).

**Why this is the right call:** it delivers real, measurable inference tuning
today (consistent with DOC_TRUST.md "runnable code over marketing docs") without
fabricating a re-quantization pipeline that cannot work against GGUF/Ollama.

**Backlog (only if the backend changes):** genuine INT8/pruning/distillation
becomes relevant *only* if the project adds an in-process PyTorch/transformers
inference path with a training/calibration loop — not applicable to Ollama GGUF.

#### 1.2b Ollama auto-optimization wiring ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (7/7 new unit tests pass; 60/60 across the
whole session suite).

**Motivation:** The 1.2a `RuntimeOptimizer` computed hardware-aware options but
nothing consumed them. This wires it into the actual inference path so real
requests are tuned to the machine automatically.

**What shipped:**

- `core/engines/ollama_integration.py` — `OllamaIntegration.__init__` gains
  `auto_optimize: bool = True`. On init it calls `RuntimeOptimizer().recommend_
  params().as_options()` and stores the result in `self.runtime_options`
  (`num_ctx` / `num_gpu` / `num_thread`).
- Those options are merged as a **base layer** into both `generate()` and
  `generate_stream()` payloads, so explicit per-call args/kwargs
  (`num_predict`, `temperature`, `top_p`, or an explicit `num_ctx`) always
  override them.
- Module-level `_detect_runtime_options()` helper with the same direct-file-load
  fallback used elsewhere (bypasses the pre-existing eager-import error in the
  top-level `thinkmesh_core/__init__.py`). It **never raises** — if the optimizer
  is unavailable it returns `{}` and Ollama's own defaults apply.
- `auto_optimize=False` disables the behavior entirely (empty base options). The
  existing HRM engine call site (`core/engines/hrm_engine.py`) uses keyword args
  and is unchanged, so it now benefits automatically.
- `tests/test_ollama_autooptimize.py` — 7 tests (options detected on init;
  `auto_optimize=False` yields empty; base options merged into the request;
  explicit kwargs override base; no-optimize uses Ollama defaults; graceful
  degradation; stream merge). HTTP layer mocked — no network.

#### 1.2c Mobile Compiler — honest TensorRT/NNAPI detection ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (11/11 new unit tests pass; 71/71 across
the whole session suite).

**Provenance / DOC_TRUST note:** the pre-existing `Phase2Optimizer`
(`thinkmesh_core/localai/phase2_optimizer.py`) *claimed* TensorRT was available
whenever CUDA existed, and reported NNAPI on any Linux whose `/proc/version`
merely contained the word "android". Both are inaccurate. Neither sibling repo
(`TwoSoul-Mobile-AI-Assistant`, `universal-soul-ai`) ships a real
`mobile_compiler` — TwoSoul's optimizer is training-time PyTorch surgery,
unrelated to on-device compilation. So the feasible, honest deliverable is
**accurate capability detection**, not a fabricated compile pipeline.

**What shipped:**

- `thinkmesh_core/localai/phase2_optimizer.py` — new probes replacing the
  assumptions:
  - `_detect_tensorrt()` — reports TensorRT only when the `tensorrt` Python
    package imports **or** `trtexec` is on PATH (via `shutil.which`). CUDA alone
    no longer implies TensorRT.
  - `_detect_nnapi()` — reports NNAPI only on a genuine Android runtime
    (`ANDROID_ROOT`/`ANDROID_DATA`/`ANDROID_STORAGE` env markers, or an
    Android-specific `/proc/version` toolchain signature), so desktop Linux is
    not misreported.
  - `get_capabilities()` — structured, honest snapshot (availability +
    version/marker detail) distinct from the mock `optimize_*` results.
- The `optimize_for_tensorrt/nnapi` methods stay integration **stubs** (real
  conversion needs the TensorRT SDK / Android NDK, unavailable on desktop) but
  now carry `'stub': True` so callers can distinguish mock from real results,
  and their docstrings say so. Invalid `Dict[str]` annotations fixed to
  `Dict[str, Any]`.
- `tests/test_phase2_optimizer.py` — 11 deterministic tests (probes
  monkeypatched): detection never raises; TensorRT not assumed from CUDA;
  reported when probe succeeds and wins active-accelerator priority; NNAPI False
  off-Android; `get_capabilities()` shape; `optimize_*` error-when-unavailable
  and stub-when-available; recommendations include general items.

**Verified live:** on this CUDA machine, `active_accelerator` is now `cuda` (not
falsely `tensorrt`); TensorRT and NNAPI both correctly report unavailable.

**Original plan (below):**

**Adopt from:** `TwoSoul-Mobile-AI-Assistant/optimization/`

**What to integrate:**
```python
# New: Universal-AI-Soul-Unlimited/optimization/
├── quantization_optimizer.py    # INT8, mixed precision
├── pruning_optimizer.py         # Model compression
├── knowledge_distillation.py    # Model size reduction
├── mobile_compiler.py           # Platform-specific optimization
└── thermal_manager.py           # Power & thermal optimization
```

**Current Gap:** Universal-AI-Soul-Unlimited has basic model optimization but lacks:
- Advanced quantization strategies
- Thermal/power management
- Systematic compression pipeline

**Benefits:**
- Reduce model size by 75% (target)
- Improve inference speed 3x
- Better battery life on mobile
- Thermal throttling prevention

**Implementation Priority:** HIGH (Week 2-4)

**Integration:**
- Enhance `thinkmesh_core/localai/model_optimizer.py`
- Add to Android APK build pipeline
- Create mobile-specific optimization profiles

---

### 1.3 Values-Based Reasoning System ⭐ MEDIUM VALUE

**Adopt from:** `TwoSoul-Mobile-AI-Assistant/twosoul/values/`

**What to integrate:**
```python
# Enhance: Universal-AI-Soul-Unlimited/core/
├── values/
│   ├── content_filter.py        # Family-safe filtering (NEW)
│   ├── intervention_engine.py   # Location/context interventions (NEW)
│   ├── privacy_manager.py       # Enhanced privacy controls (NEW)
│   └── values_engine.py         # Enhanced from TwoSoul
```

**Current State:** Universal-AI-Soul-Unlimited has basic values/onboarding
**TwoSoul Addition:** More sophisticated content filtering + location-based interventions

**Benefits:**
- Better family safety features
- Location-aware assistance
- More granular privacy controls
- Values-aligned responses

**Implementation Priority:** MEDIUM (Week 5-6)

---

## Phase 2: Enterprise Features (universal-soul-ai)

### 2.1 Premium Voice System ⭐ CRITICAL VALUE

#### 2.1a Local-first Voice Activity Detection ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (5/5 unit tests pass).

**What shipped:** The main project already had a mature **local** voice stack
(`core/voice_pipeline/desktop_voice.py`: Edge/pyttsx3/XTTS TTS + faster/openai
Whisper STT). The genuinely missing, local-first piece from
`universal-soul-ai/thinkmesh_core/voice/providers.py` was **voice activity
detection**. Its ElevenLabs/Deepgram providers are *cloud* (opt-in premium, not
default per VISION.md) and their "local fallbacks" were placeholders (silence /
dummy text), so we adopted only the reusable local part — Silero VAD with an
energy-based fallback:

- `core/voice_pipeline/vad.py` — `VoiceActivityDetector` + `VADConfig` /
  `VADResult`: prefers Silero (torch.hub, local) and always falls back to an
  adaptive RMS energy detector needing only numpy. No cloud dependency.
- Wired into `thinkmesh_core/voice/voice_pipeline.py` via
  `VoiceConfig.enable_vad` + `VoicePipeline.has_speech()`, and exported from
  `thinkmesh_core/voice/__init__.py`.
- `tests/test_vad.py` — 5 pytest tests (deterministic energy path).
- `requirements-voice.txt` — documented optional torch for Silero.

#### 2.1b Premium cloud voice tier + local noise suppression ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (13/13 new unit tests pass; 18/18 with 2.1a).

**What shipped (rest of 2.1):**

- `core/voice_pipeline/cloud_providers.py` (NEW) — `ElevenLabsTTSProvider`
  (TTS) and `DeepgramSTTProvider` (STT) as **strictly opt-in** cloud providers.
  A provider is *inactive* unless an API key is supplied (via config or the
  `ELEVENLABS_API_KEY` / `DEEPGRAM_API_KEY` env vars) **and** `privacy_mode` is
  disabled. Every call degrades to the local engine (Whisper/Coqui) on any error
  — unlike the reference's placeholder fallbacks (silence / dummy text), we pass
  the real local engine as the fallback.
- `core/voice_pipeline/audio_processor.py` (NEW) — `AudioProcessor` /
  `AudioProcessorConfig`: **local** noise suppression (spectral subtraction +
  auto-gain) for mic input and output enhancement (soft compression + voice-band
  EQ) for synthesized speech. numpy-only, with an optional scipy path. No cloud.
- Wired into `thinkmesh_core/voice/voice_pipeline.py`: `VoiceConfig` gains
  `enable_cloud_tts/stt`, `elevenlabs/deepgram_api_key`,
  `enable_noise_suppression`, `enable_output_enhancement`. `transcribe()` runs
  input cleanup then routes to the active provider (cloud→local fallback);
  `synthesize()` routes then applies output enhancement. Exposed via
  `get_status()` and exported from `thinkmesh_core/voice/__init__.py`.
- `tests/test_audio_processor.py` (6) + `tests/test_cloud_providers.py` (7) —
  deterministic, no network. `requirements-voice.txt` documents the opt-in tier.

**Design note:** local stays the **default** everywhere; enabling cloud requires
an explicit `privacy_mode=False` + enable flag + key, so there are no surprise
cloud calls (consistent with VISION.md and DOC_TRUST.md).

#### 2.1c Local premium tier via OmniVoice Studio ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (6/6 new unit tests pass; 47/47 across the
whole session suite).

**Motivation:** For a stronger *local* premium voice option (better cloning /
quality than the built-in Coqui/Whisper) without sending audio to a third party,
we integrate [OmniVoice Studio](https://github.com/debpalash/OmniVoice-Studio) —
an on-device, OpenAI-compatible voice studio — as an **optional local backend**.

**License boundary (important):** OmniVoice Studio is **AGPL-3.0**. We do **not**
vendor any of its code; we talk to its OpenAI-compatible HTTP API on a **separate
local process** (`http://localhost:3900/v1` by default). HTTP calls to an
independent process are mere aggregation, so this does **not** impose AGPL on
this project. If OmniVoice code were ever linked/embedded, AGPL would apply — so
we deliberately keep the boundary at the network interface.

**What shipped:**

- `core/voice_pipeline/cloud_providers.py` — `OmniVoiceTTSProvider`
  (`POST /v1/audio/speech`) and `OmniVoiceSTTProvider`
  (`POST /v1/audio/transcriptions`). **Local, opt-in, no API key.** Same
  interface as the cloud providers (`available`, `synthesize`/`transcribe` with
  `local_fallback`, `shutdown`), so they slot into the pipeline unchanged and
  degrade to Whisper/Coqui when the local server isn't running.
- `thinkmesh_core/voice/voice_pipeline.py`: `VoiceConfig` gains
  `enable_omnivoice_tts/stt` and `omnivoice_base_url`. Because audio stays
  on-device, these are **NOT** gated on `privacy_mode` (unlike the cloud tier).
  Registered under the `omnivoice` provider key; surfaced in `get_status()` as
  `omnivoice_tts_active` / `omnivoice_stt_active`.
- Base URL override via `OMNIVOICE_BASE_URL`. Exported from
  `thinkmesh_core/voice/__init__.py`.
- `tests/test_cloud_providers.py` — 6 added tests (default localhost URL, env
  override, no-key requirement, server-down local fallback). No network.

**Original plan (rest of 2.1 below):**

**Adopt from:** `universal-soul-ai/thinkmesh_core/voice/`

**What to integrate:**
```python
# Enhance: Universal-AI-Soul-Unlimited/core/voice_pipeline/
├── elevenlabs_integration.py    # Studio-quality TTS (NEW)
├── deepgram_integration.py      # 95%+ accuracy STT (NEW)
├── silero_vad.py               # Voice activity detection (NEW)
├── noise_suppression.py        # Audio cleanup (NEW)
└── voice_personality.py        # Personality-aware speech (ENHANCE)
```

**Current Gap:** Universal-AI-Soul-Unlimited uses Edge TTS + XTTS cloning
**Missing:** Professional-grade voice quality, advanced STT

**Benefits:**
- Studio-quality voice output
- Much better speech recognition
- Real-time noise cancellation
- Professional user experience

**Implementation Priority:** CRITICAL (Week 3-5)

**Integration:**
- Add as optional premium tier (requires API keys)
- Keep Edge TTS as free fallback
- Privacy mode: use only local options

---

### 2.2 Enhanced Multi-Agent Orchestration ⭐ HIGH VALUE

**Adopt from:** `universal-soul-ai/thinkmesh_core/orchestration/`

**What to integrate:**
```python
# Enhance: Universal-AI-Soul-Unlimited/thinkmesh_core/orchestration/
├── orchestrator.py (ENHANCE with 6 strategies)
│   - Sequential, Parallel, Hierarchical
│   - Consensus, Competitive, Collaborative
├── agent_pool.py (ENHANCE agent selection)
├── collective_intelligence.py (NEW)
└── consensus_engine.py (NEW)
```

**Current State:** Basic ThinkMesh adapter exists
**Enhancement:** More sophisticated orchestration strategies

**Benefits:**
- Better agent collaboration
- Consensus mechanisms for accuracy
- Performance-based agent selection
- Adaptive strategy selection

**Implementation Priority:** HIGH (Week 4-6)

---

### 2.3 Android Overlay System ⭐ HIGH VALUE

#### 2.3a Feasibility assessment (July 16, 2026) — deferred, not desktop-testable

**Decision:** Not implemented in this pass. Prioritized AES-256 (2.5a) instead,
which is fully implementable and testable in this desktop (Windows/Python 3.11)
environment. The Android overlay is inherently a **mobile-build artifact** and
cannot be validated here:

- The reference `universal-soul-ai/android_overlay/` implements an 8-direction
  360° gesture overlay (`core/gesture_handler.py`: N=Calendar, E=Transcription,
  W=Notes, …) but depends on `pyjnius`/`jnius` (Java↔Android bridge),
  `SYSTEM_ALERT_WINDOW` permission, and the Android lifecycle. `jnius` is
  unavailable on Windows (needs JAVA_HOME + Android SDK), and `buildozer` APK
  builds require WSL/Linux/Docker/CI.
- Only the **pure gesture math** (swipe angle/distance/velocity thresholds) is
  platform-agnostic and unit-testable on desktop; the overlay runtime is not.

**Recommended path when picked up:** port the gesture-classification logic as a
platform-independent module with desktop unit tests, and gate the `jnius`/overlay
layer behind an Android-only import guard, validated via GitHub Actions APK build
+ Android emulator (not on this host).

**Adopt from:** `universal-soul-ai/android_overlay/`

**What to integrate:**
```python
# New: Universal-AI-Soul-Unlimited/android_overlay/
├── universal_soul_overlay.py    # 360° gesture overlay (NEW)
├── voice_personality/           # On-device voice (NEW)
├── core/                        # Overlay engine (NEW)
└── ui/                          # Minimalist overlay UI (NEW)
```

**Current Gap:** Universal-AI-Soul-Unlimited has overlay config only (not implemented)
**universal-soul-ai:** Working 360° gesture recognition overlay

**Benefits:**
- Always-available assistant overlay
- Gesture-based interaction
- System-wide accessibility
- Modern mobile UX

**Implementation Priority:** HIGH (Week 6-9)

**Note:** This directly addresses "Android 360° overlay (config only)" gap in PROJECT_STATUS.md

---

### 2.4 GUI Automation Suite ⭐ MEDIUM VALUE

**Adopt from:** `universal-soul-ai/` (automation dependencies)

**What to integrate:**
```python
# Enhance: Universal-AI-Soul-Unlimited/core/automation/
├── screen_automation.py     # PyAutoGUI, screen control (NEW)
├── browser_automation.py    # Selenium, Playwright (NEW)
├── ocr_engine.py           # ENHANCE existing with EasyOCR
├── computer_vision.py      # YOLO object detection (NEW)
└── real_actions.py         # ENHANCE with more actions
```

**Current State:** Basic CoAct sandbox (file operations)
**Enhancement:** Full desktop/browser automation

**Benefits:**
- Real task automation beyond files
- Browser control for web tasks
- Screen understanding via OCR
- Visual element detection

**Implementation Priority:** MEDIUM (Week 7-10)

**Note:** Addresses "Bundled PaddleOCR (optional import)" and "Broad CoAct" gaps

---

### 2.5 Enterprise Security & Compliance ⭐ MEDIUM VALUE

#### 2.5a AES-256 encryption-at-rest ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (9/9 unit tests pass, incl. tamper
detection and wrong-passphrase rejection).

**Provenance / DOC_TRUST note:** the reference
`universal-soul-ai/thinkmesh_core/sync/encrypted_backup.py` `EncryptionManager`
uses **XOR** with a SHA-256-of-device-id "key" — that is **not encryption**
(trivially reversible, unauthenticated, and its own comments say "use proper
encryption in production"). We did **not** adopt it. Instead we implemented
genuine authenticated encryption.

**What shipped:**

- `thinkmesh_core/sync/encryption.py` (NEW) — `AESEncryptor`:
  **AES-256-GCM** with a per-encryption random 96-bit nonce and 16-byte salt,
  **PBKDF2-HMAC-SHA256** key derivation (200k iterations) from a user
  passphrase. Self-describing envelope (magic/version/salt/nonce/ciphertext+tag).
  Helpers: `encrypt`/`decrypt`, `encrypt_json`/`decrypt_json`,
  `encrypt_file`/`decrypt_file(_json)`. Uses the already-declared `cryptography`
  package. GCM provides integrity, so tampering and wrong keys are detected.
- Exported from `thinkmesh_core/sync/__init__.py`.
- `tests/test_encryption.py` — 9 deterministic tests (fast KDF iterations).

**2.5 status:** memory persistence wired (2.5b), audit logging delivered (2.5c),
audit wiring for automation + household config delivered (2.5d), and enterprise
auth delivered (2.5e below). Android overlay remains deferred (mobile-build
artifact, not desktop-testable).

#### 2.5b Encryption-at-rest for shared session memory ✅ DELIVERED (July 16, 2026)

**Status:** Implemented and validated (6/6 new unit tests pass; 60/60 across the
whole session suite).

**Motivation:** Consume the 2.5a primitive to protect the conversation history
that is actually written to disk — `core/memory/shared_session.py`'s JSONL store
— as **opt-in, off-by-default** encryption-at-rest.

**What shipped:**

- `core/memory/shared_session.py` — passphrase read from
  `SHARED_MEMORY_PASSPHRASE`. **Unset ⇒ plaintext JSONL, byte-for-byte
  unchanged** (local-first default). When set, each line is written as an
  `enc:v1:` base64 AES-256-GCM envelope; `recent_turns()` decrypts transparently.
- `_CachedKeyEncryptor` derives the PBKDF2 key **once** per process (200k
  iterations retained) then does fast per-line AES-GCM with a fresh random nonce
  per line — avoiding a ~4.6s-per-read cost while keeping full KDF strength.
- Reads tolerate **legacy plaintext lines**, so enabling encryption never orphans
  existing history; a wrong passphrase yields no readable turns (tamper-safe).
- Direct-file-load fallback for the primitive (same pattern as elsewhere) to
  bypass the top-level `thinkmesh_core/__init__.py` eager-import error.
- `tests/test_shared_session_encryption.py` — 6 tests (plaintext default
  round-trip; encrypted round-trip with plaintext absent from disk bytes;
  wrong-passphrase yields nothing; no-passphrase skips encrypted lines; legacy
  plaintext readable after enabling; context block over encrypted turns).

#### 2.5c Local-first audit logging ✅ DELIVERED (July 17, 2026)

**Status:** Implemented and validated (11/11 new unit tests pass; smoke script
green; full suite still green).

**Provenance / DOC_TRUST note:** the reference `universal-soul-ai` ships a
structured JSON logging system (`thinkmesh_core/logging.py`) with a
`PrivacyAwareFilter` and per-event helpers, but there is **no dedicated audit
trail module** in its code (no `audit_logger.py` / `enterprise_audit.py` — the
"Compliance audit trails" line in the plan below was aspirational). The main
project only had a *narrow* automation audit (`core/automation/real_actions.py`
→ `data/automation_audit.jsonl`). So the honest, feasible deliverable is a
**general, reusable audit trail** that consumes the already-shipped AES-256-GCM
primitive (2.5a) and mirrors the local-first, opt-in-encryption pattern of the
session store (2.5b) — not a re-skin of a logging façade.

**What shipped:**

- `core/security/audit_logger.py` (NEW) — append-only JSONL trail at
  `data/audit/audit.jsonl`, one structured event per line
  (`id, ts, category, action, actor, target, outcome, severity, detail`).
  Public API: `log_event()` (alias `audit()`), `read_events()`, `tail()`,
  `query()` (category/action/actor/outcome/time-window filters). `log_event`
  **never raises** — a failed write is logged and swallowed so auditing can't
  break a caller.
  - **Local-first / plaintext by default**; opt-in **AES-256-GCM at rest** via
    the `AUDIT_LOG_PASSPHRASE` env var, reusing the shared-session
    `_CachedKeyEncryptor` (`enc:v1:` envelope, key derived once, fresh nonce per
    line). Reads tolerate mixed legacy-plaintext + encrypted lines and corrupt
    lines; wrong/absent passphrase yields no readable encrypted events.
  - **Privacy-aware redaction**: sensitive keys (password, passphrase, secret,
    token, api_key, credential, private_key, cookie, ssn, credit_card, …) are
    recursively replaced with `***REDACTED***` **before** anything is written,
    so the audit trail never becomes a secondary secret leak.
- `core/security/__init__.py` (NEW) — package exports.
- `tests/test_audit_logger.py` — 11 deterministic tests (plaintext round-trip;
  category normalization; nested privacy redaction with no disk leakage;
  encrypted round-trip; wrong-passphrase yields nothing; no-passphrase skips
  encrypted lines; legacy-plaintext readable after enabling; query filters &
  time window; tail/limit ordering; corrupt-line tolerance; never-raises).
- `scripts/smoke_adoption.py` — new `check_audit_logging()` section.

**First real call site wired:** `core/family/household.py` `verify_member()` (the
privacy-wall PIN gate) now emits an `auth` / `pin_verify` event on every check —
`success`, wrong-PIN `failure` (severity `warning`), and unknown-member
`failure`. Emission goes through a **guarded lazy import** (`_audit_auth`) that
swallows any error, so a missing/broken security package can never stop PIN
verification; the return contract is unchanged and **no PIN value is ever
passed to the audit event**. Covered by `tests/test_household_audit.py` (5
tests: success/wrong-PIN/unknown-member outcomes, no PIN on disk, and the
helper swallowing an injected `log_event` failure).

#### 2.5d Audit wiring: automation mirror + household config events ✅ DELIVERED (July 17, 2026)

**Status:** Implemented and validated (7 new tests across
`tests/test_household_audit.py` and `tests/test_automation_audit_mirror.py`; full
suite green).

**Motivation:** Give the unified security trail (2.5c) a single, cross-cutting
view of the two remaining security-relevant surfaces — automation actions and
household config changes — without disturbing their existing domain logs or
return contracts.

**What shipped:**

- **Automation mirror** — `core/automation/real_actions.py` `append_audit()`
  still writes its narrow `data/automation_audit.jsonl` entry unchanged, then
  additionally mirrors the event into the unified trail via a guarded
  `_mirror_to_security_audit()` helper: `category='automation'`, action from the
  entry, `actor` = source, `outcome` success/failure (with matching severity),
  `target` = `path` or `dest`. The mirror is a **guarded lazy import** that
  swallows any error, so a missing/broken security package can never break
  automation. `detail` carries only `consent`, `description`, and
  `error_message` — no raw payloads.
- **Household config events** — a guarded `_audit_config()` helper emits
  `category='config'` events from `update_context` (`context_update`, with the
  list of changed field names only), `upsert_member` (`member_add` /
  `member_update`, `detail={role, pin_set}` — **never the PIN value**), and
  `remove_member` (`member_remove`). Return contracts are unchanged.
- `tests/test_automation_audit_mirror.py` (NEW) — 4 tests: success mirror,
  failure mirror (outcome + severity), `dest` used as target when no `path`, and
  the mirror never breaking `append_audit` when `log_event` raises.
- `tests/test_household_audit.py` — 3 new config tests (context-update fields,
  member add/update with `pin_set` and no PIN on disk, member-remove).

#### 2.5e Enterprise auth — local-first JWT-style tokens ✅ DELIVERED (July 17, 2026)

**Status:** Implemented and validated (10/10 new unit tests pass; smoke script
green). This closes the last outstanding 2.5 backlog item (enterprise auth).

**Motivation:** Provide token-based gating for local/enterprise features without
pulling in an external JWT library or an external identity provider — consistent
with the project's local-first, minimal-dependency stance.

**What shipped:**

- `core/security/auth.py` (NEW) — self-contained, **stdlib-only** signed tokens.
  Compact `header.payload.signature` (base64url) strings signed with
  **HMAC-SHA256**. Public API: `issue_token()`, `verify_token()`, `TokenError`.
  - Claims: `sub`, `roles`, `iat`, `exp`, `jti`; caller `extra` claims are
    allowed but **cannot override** structural fields (reserved claims win).
  - Verification checks structure, signature (**constant-time**
    `hmac.compare_digest`), and expiry (`current >= exp` ⇒ expired), and emits
    `auth` audit events (`token_issue`, `token_verify` success/failure).
  - Signing secret from `AUTH_SIGNING_SECRET`; if unset, an **ephemeral
    per-process** secret is generated (fails safe rather than shipping a
    hard-coded key). Symmetric, local verification only — no server round-trip.
- Exported from `core/security/__init__.py`
  (`issue_token`, `verify_token`, `TokenError`).
- `tests/test_auth.py` (NEW) — 10 deterministic tests (injected `now`): round-trip
  claim preservation, three-part compact format, expiry, boundary exclusivity,
  tamper rejection, wrong-secret rejection, malformed-token rejection, extra
  claims not overriding structural fields, and audit events on issue/verify
  (success and failure).
- `scripts/smoke_adoption.py` — new `check_auth_tokens()` section
  (issue/verify + expiry + tamper rejection).

**Adopt from:** `universal-soul-ai/thinkmesh_core/enterprise_*.py`

**What to integrate:**
```python
# New: Universal-AI-Soul-Unlimited/core/security/
├── encryption_manager.py    # AES-256 at rest (NEW)
├── auth_manager.py          # JWT, OAuth (NEW)
├── audit_logger.py          # Compliance audit trails (ENHANCE)
└── privacy_engine.py        # GDPR/compliance (NEW)
```

**Current Gap:** "AES-256 at rest / full encrypted cloud sync" not implemented
**universal-soul-ai:** Full encryption + enterprise auth

**Benefits:**
- Real encryption for sensitive data
- Enterprise-grade security
- Compliance readiness (GDPR, SOX)
- Secure multi-device sync

**Implementation Priority:** MEDIUM (Week 8-11)

**Note:** Directly addresses AES-256 gap in PROJECT_STATUS.md

---

## Phase 3: Integration & Polish

### 3.1 Unified Configuration System

Merge configuration approaches:
- Universal-AI-Soul-Unlimited's `config/universal_soul.json`
- universal-soul-ai's enterprise config
- Add tiered feature flags (free/premium/enterprise)

### 3.2 Comprehensive Testing

Adopt testing patterns from all projects:
- TwoSoul's benchmark tests
- universal-soul-ai's comprehensive test suite
- Integration tests across new features

### 3.3 Documentation Consolidation

- Update VISION.md with new capabilities
- Update PROJECT_STATUS.md completion estimates
- Create feature-specific guides

---

## Priority Matrix

| Feature | Value | Effort | Priority | Phase |
|---------|-------|--------|----------|-------|
| Benchmarking Suite | HIGH | LOW | 🔴 P1 | 1 |
| Premium Voice | CRITICAL | MEDIUM | 🔴 P1 | 2 |
| Optimization Engine | HIGH | MEDIUM | 🔴 P1 | 1 |
| Android Overlay | HIGH | HIGH | 🟡 P2 | 2 |
| Multi-Agent Enhance | HIGH | MEDIUM | 🟡 P2 | 2 |
| AES-256 Security | MEDIUM | MEDIUM | 🟡 P2 | 2 |
| GUI Automation | MEDIUM | HIGH | 🟢 P3 | 2 |
| Values System | MEDIUM | LOW | 🟢 P3 | 1 |

---

## Recommended Starting Point

**Quick Wins (Week 1):**
1. ✅ Benchmarking Suite (TwoSoul) - measure baseline
2. ✅ Values/Content Filter (TwoSoul) - easy integration

**High Impact (Week 2-5):**
3. ✅ Premium Voice (universal-soul-ai) - major UX upgrade
4. ✅ Optimization Engine (TwoSoul) - performance gains

**Fill Critical Gaps (Week 6-11):**
5. ✅ Android Overlay (universal-soul-ai) - completes roadmap item
6. ✅ AES-256 Security (universal-soul-ai) - completes roadmap item

---

## Vision & Roadmap Gap Analysis

Beyond the shippable features above, a review of each project's vision/roadmap
docs surfaced **future-looking capabilities** not yet in our plan. These are
longer-horizon (not week-1 work) but define the "Ultimate Soul" end-state.

### From TwoSoul (`docs/00-executive-summary.md`, `docs/04-implementation-roadmap.md`)

Aspirational performance-leadership targets. Treat as **directional**, not
commitments — TwoSoul is early stage (2 commits) and these are unproven.

| Capability | Notes | Adopt as |
|------------|-------|----------|
| MLPerf / AI Benchmark / AnTuTu targets | <10ms P95, 60+ TOPS/W, <500MB | KPIs for our benchmark suite (1.1) |
| Neural Architecture Search (NAS) | Hardware-aware model search | Backlog — needs benchmark baseline first |
| Custom NPU / GPU / SIMD kernels | >80% NPU utilization | Backlog — after quantization/pruning land |
| Thermal-aware scheduling | 90% perf retention @ 10min | Fold into `thermal_manager.py` (1.2) |
| Predictive memory management | Smart caching/compression | Backlog — mobile-focused |

### From universal-soul-ai (`zero_dependency_enhancement_roadmap.md`, `COMPREHENSIVE_ARCHITECTURE_ANALYSIS.md`)

Aligns strongly with our **privacy-first, local-first** VISION.md. Highest-fit
future work.

| Capability | Notes | Priority |
|------------|-------|----------|
| **Zero-dependency voice** (Whisper + Coqui + Silero) | Replace cloud TTS/STT with 100% local | 🔴 Directly supports VISION §4/§7 |
| **Self-hosted vision** (BLIP-2 / LLaVA / CLIP) | Local UI/screen understanding | 🟡 Enables overlay + OCR gaps |
| **Multi-modal fusion** (voice + vision + reasoning) | "Click the blue button top-right" | 🟡 After voice + vision land |
| **Predictive automation engine** | Local pattern/intent prediction | 🟢 Backlog |
| **Local knowledge graph** | Self-building from interactions | 🟢 Backlog — pairs with memory |
| **AI-enhanced error recovery** | Local reasoning over failures | 🟡 Fold into CoAct hardening |
| Federated learning (privacy-preserving) | Learn globally, keep data local | 🟢 Long-horizon / research |
| Quantum-inspired optimization | Speculative | ⚪ Research only |
| AR/VR local processing | Speculative | ⚪ Research only |

### universal-soul-ai known issues to avoid inheriting

From `IMPROVEMENT_ACTION_PLAN.md` (their own test results) — if we adopt their
code, port the **fixes**, not the bugs:

- Cross-platform compatibility was 0% (platform confidence not calibrated)
- Error recovery methods were stubbed (`_break_into_steps_recovery`, etc.)
- Confidence scoring uncalibrated
- OCR deps (EasyOCR/Tesseract) not bundled

---

## Reconciliation with VISION.md / PROJECT_STATUS.md

Mapping adoption items to existing stated gaps (single source of truth):

| VISION/STATUS gap | Addressed by |
|-------------------|--------------|
| AES-256 at rest (Missing) | 2.5 Enterprise Security |
| 360° overlay (Missing, config only) | 2.3 Android Overlay |
| Bundled OCR (Missing) | 2.4 GUI Automation |
| Broad CoAct beyond sandbox (Partial) | 2.4 + AI-enhanced error recovery |
| Encrypted cloud sync (Partial) | 2.5 Enterprise Security |
| Native Android GGUF (Missing) | 1.2 Optimization + zero-dep voice/vision |
| ElevenLabs/Deepgram not primary (Partial) | 2.1 Premium Voice **and** zero-dep local option |

**Key tension:** Premium Voice (2.1, cloud APIs) vs. zero-dependency voice
(local Whisper/Coqui). VISION.md is local-first — so **local should be the
default**, cloud premium an opt-in tier. Recommend building the local stack as
the primary path and treating ElevenLabs/Deepgram as optional enhancement.

---

## Next Steps

1. Review and approve this adoption plan (including the vision-gap section)
2. Select starting features (recommend: Benchmarking + local-first voice)
3. Create feature branches for each integration
4. Implement incrementally with tests
5. Update PROJECT_STATUS.md / VISION.md status map as features complete

**Awaiting your direction on which features to implement first.**


