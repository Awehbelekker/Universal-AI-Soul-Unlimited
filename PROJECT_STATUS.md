# Project Status (Source of Truth)

**Last updated:** July 2026  
**Product vision (end-state):** [VISION.md](VISION.md)  
**Canonical shipped state:** [BETA_VERSION_INFO.md](BETA_VERSION_INFO.md) + [main.py](main.py) / [app_main.py](app_main.py)

---

## Completion estimates

| Layer | ~Complete |
|-------|-----------|
| Core engine modules | 75% |
| Desktop end-to-end | 70% |
| thinkmesh_core integration | 55% |
| Android production app | 40% |
| Tests / CI alignment | 50% |
| **Ultimate Soul (vs VISION.md)** | **~45–55%** |

---

## What works

- `python main_desktop.py` — Ollama chat with streaming, adaptive routing, memory
- Persisted values / personality in `data/user_profiles/` + CLI `onboard` / `values`
- Desktop voice: **Edge neural TTS** default; **XTTS cloning** via `voice clone <wav>` after `python scripts/setup_voice_clone.py`
- Offline STT: **faster-whisper** preferred for `listen` / mic; Google recognition only as fallback
- CoAct real slice: `automate list|read|open|note|append|mkdir|copy|delete|info` (sandbox, consent + audit)
- Android thin client: Settings screen for Ollama URL/model, persist + Test connection (`app_main.py`)
- **PWA thin client**: `web/` + `python scripts/serve_pwa.py` (phone browser installable; Ollama CORS proxy)
- ThinkMesh multipass: planner → critic → synthesizer on deep routes; CLI `think <question>`
- `python smoke_test_ollama.py` / `python scripts/setup_ollama.py`
- Benchmark suite under `benchmarks/`
- GitHub Actions APK + benchmark workflows
- ThinkMesh adapter wired to local `thinkmesh_core` orchestrator

## What does not work yet

- On-device GGUF inference in Android APK (needs strategy decision + heavy deps)
- Android 360° overlay (config only, no code)
- Bundled PaddleOCR (runtime optional import in `core/automation/ocr_engine.py`)
- Full personality/values assessment services (CLI/onboarding covers basics)
- First XTTS model download (~2GB) on first clone — may take a while; CPML non-commercial terms apply
- Broad CoAct / TerminalBench still largely simulated beyond sandbox file actions
- AES-256 encryption (config flag only)

Full Done / Partial / Missing map: [VISION.md](VISION.md#status-map-july-2026).

## Documentation disclaimer

Files named `*_COMPLETE.md` or claiming "Production Ready" may be **aspirational**. Trust [VISION.md](VISION.md) for intent, this file for shipped reality, and runnable code over marketing docs.

## Next milestones

1. Install PWA on a phone (Add to Home Screen) and confirm LAN chat
2. Optional: APK build if native Android still desired
3. Optional: on-device models, overlay / OCR / sync / crypto
