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
| thinkmesh_core integration | 40% |
| Android production app | 30% |
| Tests / CI alignment | 50% |
| **Ultimate Soul (vs VISION.md)** | **~45–55%** |

---

## What works

- `python main_desktop.py` — Ollama chat with streaming, adaptive routing, memory
- Persisted values / personality in `data/user_profiles/` + CLI `onboard` / `values`
- Desktop voice: **Edge neural TTS** default; **XTTS cloning** via `voice clone <wav>` after `python scripts/setup_voice_clone.py`
- `python smoke_test_ollama.py` / `python scripts/setup_ollama.py`
- Benchmark suite under `benchmarks/`
- GitHub Actions APK + benchmark workflows
- ThinkMesh adapter wired to local `thinkmesh_core` orchestrator

## What does not work yet

- On-device GGUF inference in Android APK (needs strategy decision + heavy deps)
- Android 360° overlay (config only, no code)
- Bundled PaddleOCR (runtime optional import in `core/automation/ocr_engine.py`)
- Full personality/values assessment services (CLI/onboarding covers basics)
- Offline Whisper STT (mic uses Google recognition by default)
- First XTTS model download (~2GB) on first clone — may take a while; CPML non-commercial terms apply
- Real CoAct OS execution (still simulated)
- AES-256 encryption (config flag only)

Full Done / Partial / Missing map: [VISION.md](VISION.md#status-map-july-2026).

## Documentation disclaimer

Files named `*_COMPLETE.md` or claiming "Production Ready" may be **aspirational**. Trust [VISION.md](VISION.md) for intent, this file for shipped reality, and runnable code over marketing docs.

## Next milestones

1. Prove voice clone end-to-end (`voice clone <wav>`)
2. Offline Whisper STT
3. One real CoAct automation path (consent + audit)
4. Android thin client reliability (network Ollama)
5. Optional: ThinkMesh depth, on-device models, overlay / OCR / sync
