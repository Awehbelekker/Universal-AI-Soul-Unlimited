# Project Status (Source of Truth)

**Last updated:** July 2026  
**Product vision (end-state):** [VISION.md](VISION.md)  
**Doc trust order:** [docs/DOC_TRUST.md](docs/DOC_TRUST.md)  
**Canonical shipped state:** [BETA_VERSION_INFO.md](BETA_VERSION_INFO.md) + [main.py](main.py) / [app_main.py](app_main.py)

---

## Completion estimates

| Layer | ~Complete |
|-------|-----------|
| Core engine modules | 75% |
| Desktop end-to-end | 72% |
| thinkmesh_core integration | 55% |
| Android production app | 40% |
| Multi-device / family / offline pack | 60% |
| Tests / CI alignment | 50% |
| **Ultimate Soul (vs VISION.md)** | **~50–58%** |

---

## What works

- `python main_desktop.py` — Ollama chat with streaming, adaptive routing, memory
- Persisted values / personality in `data/user_profiles/` + CLI `onboard` / `values`
- Desktop voice: **Edge neural TTS** default; **XTTS cloning** via `voice clone <wav>` after `python scripts/setup_voice_clone.py`
- Offline STT: **faster-whisper** preferred for `listen` / mic; Google recognition only as fallback
- CoAct real slice: `automate list|read|open|note|append|mkdir|copy|delete|info` (sandbox, consent + audit)
- Android thin client: Settings screen for Ollama URL/model, persist + Test connection (`app_main.py`)
- **PWA thin client**: `web/` + `python scripts/serve_pwa.py` — phone LAN; Speak replies; wow tools; Google OAuth/Gmail
- **Shared PC memory** (`core/memory/`) — phone + desktop chat continuity via `/api/memory` + `/api/chat`
- **Phone deep route** — deep messages trigger ThinkMesh multipass on the PC before reply
- **Family Phase A–C** (`core/family/`) — household context, members + PIN walls, board facts, reminders (PWA Family UI)
- **Offline LIGHT pack** (`core/offline/`) — cached degraded replies + queue sync when LAN returns ([docs/OFFLINE_LIGHT.md](docs/OFFLINE_LIGHT.md))
- **Security** (`core/security/`) — local-first audit trail (privacy redaction + opt-in AES), opt-in AES-256 at rest for session memory, and local HMAC-SHA256 JWT-style auth tokens
- **Family Library** (`core/library/`) — feed PDF/txt/md into PC KB; tags (`parenting`, `support`, …); ask/summarize/support grounded in excerpts
- **Storyteller voice** — parent’s own XTTS clone with mild local pitch shift; user-chosen character name only (no celebrity labels)
- **Companion emotion eyes** — PWA presence face reacts to idle/thinking/listening/speaking/emotions
- **Capacitor APK shell** (`mobile/`) — Android project + home-screen companion widget; see [docs/MOBILE_APK.md](docs/MOBILE_APK.md) (build needs JDK/Android Studio)
- ThinkMesh multipass: planner → critic → synthesizer; CLI `think <question>`
- `python scripts/smoke_roadmap.py` / other smokes under `scripts/`

## What does not work yet

- Native on-device GGUF LIGHT/STANDARD in Android APK (PWA offline pack is degraded only)
- Pre-built APK binary in-repo (scaffold is ready; install Android Studio to compile)
- Android 360° overlay (home widget ships; full overlay later)
- Bundled PaddleOCR (optional import)
- Full personality/values assessment service (basics + family context exist)
- Full encrypted cloud sync — E2E crypto for the offline queue (queue sync is plaintext local). AES-256 at rest now exists opt-in for session memory + audit log, but not yet for profiles/household
- Broad CoAct / TerminalBench beyond sandbox
- Family “shared Soul mesh” (Phase D) across many people as one product

Full Done / Partial / Missing map: [VISION.md](VISION.md#status-map-july-2026).

## Documentation disclaimer

Files named `*_COMPLETE.md` or claiming "Production Ready" may be **aspirational**. Trust [VISION.md](VISION.md) for intent, this file for shipped reality, [docs/DOC_TRUST.md](docs/DOC_TRUST.md) for reading order, and runnable code over marketing docs.

## Next milestones

1. Build/install Capacitor APK from [`mobile/`](mobile/) — see [docs/MOBILE_APK.md](docs/MOBILE_APK.md) (JDK 17 + Android Studio required)
2. Native Android LIGHT GGUF (optional if PWA+PC covers daily use)
3. Extend AES at rest to profiles/household + E2E encrypted sync (opt-in AES already covers session memory + audit log)
4. Family Phase D mesh only after A–C feel trusted daily
5. Overlay / OCR after companion loop polish
