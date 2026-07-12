# Universal AI Soul Unlimited

**Version:** 1.0.0-beta  
**Status:** Beta — desktop AI orchestrator + Android UI shell  
**Vision (Ultimate Soul):** [VISION.md](VISION.md) · **Shipped today:** [PROJECT_STATUS.md](PROJECT_STATUS.md)

---

## What is Universal AI Soul Unlimited?

A **local-first personal AI companion** aimed at privacy-first reasoning, memory, voice, and automation on desktop and phone. Full end-state is defined in [VISION.md](VISION.md).

Today’s stack includes:

- **HRM reasoning** — Ollama (~3B) with placeholder fallback
- **CoAct-1 automation** — routing / shell (real OS execution still limited)
- **ThinkMesh Core** — 12-module multi-agent scaffold
- **Voice** — Edge neural TTS default; Coqui XTTS cloning when set up
- **Android app** — Kivy chat UI; network Ollama when available

### Shipped today vs planned

| Component | Status |
|-----------|--------|
| Desktop orchestrator (`main_desktop.py`) | Functional with Ollama or placeholder |
| Values / personality / onboarding | Basic CLI + persisted profiles |
| Voice (Edge + optional XTTS clone) | Desktop working; clone needs a sample WAV |
| Android APK (`main.py` / `app_main.py`) | UI + AI bridge (requires runtime backend) |
| Model weights | Not in repo — download via Ollama |
| ThinkMesh / real CoAct / overlay / OCR / AES | Partial or not implemented — see [VISION.md](VISION.md) |

For honest scope see [VISION.md](VISION.md), [PROJECT_STATUS.md](PROJECT_STATUS.md), and [BETA_VERSION_INFO.md](BETA_VERSION_INFO.md).

---

## Quick Start (Desktop)

```bash
git clone https://github.com/Awehbelekker/universal-soul-ai
cd Universal-AI-Soul-Unlimited

pip install -r requirements.txt

# Install Ollama + model (recommended)
python scripts/setup_ollama.py

# Run full AI system
python main_desktop.py
```

### Without Ollama

The HRM engine falls back to a placeholder model. Responses are template-based but the pipeline still runs.

---

## Quick Start (Android)

Build requires **Linux or WSL** (Buildozer does not run natively on Windows):

```bash
buildozer -v android debug
```

Or use GitHub Actions: [.github/workflows/build-apk.yml](.github/workflows/build-apk.yml)

The APK uses a lightweight dependency set. Full on-device inference requires additional setup — see [ANDROID_BUILD_GUIDE.md](ANDROID_BUILD_GUIDE.md).

---

## Configuration

Settings live in [config/universal_soul.json](config/universal_soul.json). Key sections:

```json
{
  "hrm": {
    "backend": "ollama",
    "ollama_model": "qwen2.5:3b"
  },
  "coqui_tts": { "enabled": false },
  "memgpt": { "enabled": true },
  "terminalbench": { "enabled": true }
}
```

---

## Entry Points

| File | Purpose |
|------|---------|
| `main.py` | Re-exports `UniversalSoulAI`; launches Android UI on device, desktop CLI otherwise |
| `main_desktop.py` | Full async orchestrator |
| `app_main.py` | Kivy Android application |

---

## Architecture

```
User → main_desktop / app_main
         → HRM (Ollama | Llama.cpp | placeholder)
         → CoAct-1 (+ TerminalBench for coding tasks)
         → ThinkMesh adapter (thinkmesh_core orchestrator)
         → MemGPT memory / Coqui TTS (optional)
```

---

## Privacy

Designed for local processing. Cloud voice providers (ElevenLabs, Deepgram) are optional and disabled when `voice` privacy settings require local-only mode.

---

## License

[Add your license here]

---

## Support

- GitHub Issues: https://github.com/Awehbelekker/Universal-AI-Soul-Unlimited/issues
- Setup guide: [SETUP_RUNTIME.md](SETUP_RUNTIME.md)
