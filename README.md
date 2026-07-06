# Universal AI Soul Unlimited

**Version:** 1.0.0-beta  
**Status:** Beta — desktop AI orchestrator + Android UI shell (see [BETA_VERSION_INFO.md](BETA_VERSION_INFO.md))

---

## What is Universal AI Soul Unlimited?

A **local-first AI assistant platform** with:

- **HRM reasoning engine** — Ollama/Qwen2.5-3B with placeholder fallback
- **CoAct-1 automation** — task routing with optional TerminalBench
- **ThinkMesh Core** — 12-module multi-agent scaffold (orchestration, voice, localai, etc.)
- **Voice pipeline** — Whisper/Coqui (local) with cloud provider hooks
- **Android app** — Kivy chat UI; connects to AI backend when available

### Shipped today vs planned

| Component | Status |
|-----------|--------|
| Desktop orchestrator (`main_desktop.py`) | Functional with Ollama or placeholder |
| Android APK (`main.py` / `app_main.py`) | UI + AI bridge (requires runtime backend) |
| Model weights | Not in repo — download via Ollama or `models/model_manager.py` |
| Android overlay, PaddleOCR bundle | Not implemented |
| Personality / values / onboarding services | Stubs |

For honest scope details see [BETA_VERSION_INFO.md](BETA_VERSION_INFO.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).

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
