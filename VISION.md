# Ultimate Soul — Product Vision

**Canonical end-state for Universal AI Soul Unlimited.**  
**Last updated:** July 2026

| Document | Role |
|----------|------|
| **This file** | What “done” means (product vision) |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | What ships today (honest runtime) |
| [BETA_VERSION_INFO.md](BETA_VERSION_INFO.md) | Android beta shell scope |
| `*_COMPLETE.md` / marketing docs | Historical / aspirational — **not** source of truth |

---

## One-sentence mission

A **privacy-first personal AI companion** that knows your values, reasons locally, speaks in a natural (optionally cloned) voice, can automate real tasks, and stays with you on desktop and phone without surrendering your data.

---

## End-state product (Ultimate Soul)

### 1. Companion intelligence
- Local hierarchical reasoning (HRM) with adaptive depth
- Conversational memory that persists across sessions
- Personality modes (Professional, Friendly, Energetic, Calm, Creative, Analytical)
- Values + onboarding that shape replies and boundaries
- Family / relationship context when the user opts in

### 2. ThinkMesh multi-agent core
Twelve module pillars working as one system:

| Module | Role |
|--------|------|
| orchestration | Multi-agent strategies (sequential → adaptive) |
| ai_providers | Local / cloud / hybrid with failover |
| voice | STT + TTS, privacy modes |
| monitoring | Health and performance |
| cogniflow | Strategic planning |
| automation | Workflows and triggers |
| sync | Encrypted backup / sync |
| bridges | Optional external APIs |
| synergycore | Inter-module messaging |
| hrm | Relationship / user profiling |
| reasoning | Logical / strategic inference |
| localai | Local model lifecycle |

### 3. Intelligence tiers
| Tier | Model class | Target |
|------|-------------|--------|
| LIGHT | ~27M / tiny | Fast mobile / edge |
| STANDARD | ~3B (Ollama / GGUF) | Daily desktop + phone client |
| ADVANCED | ~20B Q4 | Desktop research / deep work |
| PREMIUM | ~20B higher quality | Optional heavy desktop |

### 4. Voice
- Default: natural neural TTS (local-first preference)
- Cloning: Coqui XTTS (or equivalent) from a short clean sample
- STT: offline Whisper by default; optional cloud (Deepgram) with consent
- Personality-aware speaking style

### 5. Automation (CoAct)
- Real task execution (files, scripts, schedules) — not simulated success
- Coding / debug path via multi-agent planner → executor → validator when useful
- Clear user consent and undo / audit trail

### 6. Platforms
| Surface | Ultimate role |
|---------|----------------|
| Desktop (`main_desktop.py`) | Full brain: models, memory, voice, automation |
| Android (`app_main.py`) | Always-with-you client; later on-device LIGHT/STANDARD |
| Overlay | Optional 360° / gesture shell (Android) |
| OCR | Optional screen/document understanding (PaddleOCR or equivalent) |

### 7. Privacy & trust
- Local-first by default; cloud only with explicit opt-in
- Real encryption for sensitive profile / memory at rest (AES-256 or better)
- Optional encrypted sync; zero forced telemetry
- User can export / delete their data

---

## Status map (July 2026)

Legend: **Done** = usable in daily desktop flow · **Partial** = code/path exists but incomplete · **Missing** = config, stub, or aspirational only

### Companion intelligence
| Capability | Status | Notes |
|------------|--------|-------|
| Desktop Ollama chat + streaming | **Done** | `main_desktop.py` |
| Adaptive routing (fast/standard/deep) | **Done** | `core/routing/` |
| Session / MemGPT-style memory | **Partial** | Works for continuity; not full MemGPT product |
| Personality modes (CLI) | **Partial** | Switchable; not full assessment service |
| Values + onboarding | **Partial** | Wizard + persist; not full 15-question service |
| Family coordination | **Missing** | Config / docs only |

### ThinkMesh
| Capability | Status | Notes |
|------------|--------|-------|
| 12 module packages present | **Partial** | Scaffold / modules on disk |
| Adapter into desktop orchestrator | **Partial** | Deep routes + `think` CLI use multipass |
| Real multi-agent product mesh | **Partial** | Planner/critic/synth over HRM/Ollama; full mesh still thin |

### Models / tiers
| Capability | Status | Notes |
|------------|--------|-------|
| STANDARD via Ollama (~3B) | **Done** | e.g. `llama3.2:3b` / Qwen |
| Placeholder fallback without Ollama | **Done** | Degraded but pipeline runs |
| LIGHT on-device (Android GGUF) | **Missing** | Strategy + heavy deps undecided |
| ADVANCED / PREMIUM 20B | **Partial** | Scripts / guides; not default path |

### Voice
| Capability | Status | Notes |
|------------|--------|-------|
| Edge neural TTS (desktop) | **Done** | Default good voice |
| Coqui / XTTS install on Windows | **Done** | `coqui-tts` via `scripts/setup_voice_clone.py` |
| Voice clone from WAV | **Partial** | CLI: `voice clone <file|record|demo>`; needs sample + first model download |
| Offline Whisper STT | **Done** | `faster-whisper` preferred; Google fallback |
| ElevenLabs / Deepgram | **Partial** | Hooks / privacy gates; not primary |

### Automation
| Capability | Status | Notes |
|------------|--------|-------|
| CoAct routing / engine shell | **Partial** | Exists; unmatched tasks still simulated |
| Real OS / file automation | **Partial** | Sandbox allowlist: list/read/open/note/append/mkdir/copy/delete + consent + audit |
| TerminalBench coding agents | **Partial** | Integration claimed; not proven end-to-end |

### Platforms
| Capability | Status | Notes |
|------------|--------|-------|
| Desktop orchestrator | **Done** | Primary product surface |
| Android chat UI | **Partial** | Kivy shell + Settings |
| Android → network Ollama | **Partial** | URL/model persist, Test, retries; needs device APK proof |
| **PWA thin client** | **Done** | Phone over LAN via `serve_pwa.py`; Settings + chat proven |
| Android on-device inference | **Missing** | |
| 360° overlay | **Missing** | Config only |
| Bundled OCR | **Missing** | Optional import only |

### Privacy
| Capability | Status | Notes |
|------------|--------|-------|
| Local-first design | **Done** | Default posture |
| AES-256 at rest | **Missing** | Flag / aspirational |
| Encrypted cloud sync | **Missing** | Module scaffold at best |
| Export / delete profile | **Partial** | Profile files exist; no polished UX |

---

## Recommended build order (to Ultimate)

1. ~~**Desktop companion polish**~~ — Edge/XTTS + `voice clone` path proven  
2. ~~**Offline STT**~~ — Whisper local for mic (`faster-whisper`; Google fallback)  
3. ~~**Real CoAct slice**~~ — sandbox allowlist + consent + audit (expand as needed)  
4. ~~**Android thin client**~~ — Settings + persisted LAN Ollama client (APK device proof still open)  
5. ~~**ThinkMesh depth**~~ — multipass planner/critic/synth on deep routes + `think` CLI  
6. **On-device LIGHT/STANDARD** — only after thin client is solid  
7. **Overlay / OCR / sync / crypto** — after core companion loop is trusted  
8. **APK device proof** — optional if PWA covers daily phone use  
9. ~~**PWA phone proof**~~ — LAN chat + Settings confirmed on mobile

---

## Non-goals (for now)

- Replacing cloud frontier models for every query  
- Shipping 20B weights inside the Android APK  
- Treating historical `*_COMPLETE.md` claims as shipped fact  

---

## How to use this file

- Plan features against the **End-state** sections.  
- Update the **Status map** when something moves Done ← Partial ← Missing.  
- Keep [PROJECT_STATUS.md](PROJECT_STATUS.md) shorter and operational; keep vision detail here.
