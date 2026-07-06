# Runtime Setup

Universal Soul AI does **not** ship model weights. Use one of these backends:

## Option A: Ollama (recommended)

1. Install [Ollama](https://ollama.com/download)
2. Run the setup script:

```bash
python scripts/setup_ollama.py
```

3. Start the desktop system:

```bash
python main_desktop.py
```

Default model: `qwen2.5:3b` (configured in `config/universal_soul.json`).

## Option B: Llama.cpp (GGUF)

1. Download a GGUF model via `models/model_manager.py` or manually
2. Set in `config/universal_soul.json`:

```json
{
  "hrm": {
    "backend": "llama_cpp",
    "model_path": "models/qwen2.5-3b-instruct-q4_k_m.gguf"
  }
}
```

3. Install: `pip install llama-cpp-python`

## Option C: Placeholder (no install)

If neither backend is available, HRM uses a template placeholder model.
The pipeline still runs for testing UI and automation wiring.

## Android

The APK uses a lightweight dependency set. For real inference on device:

- **Network Ollama**: point `hrm.ollama_url` to a LAN Ollama instance, or
- **On-device GGUF**: requires additional native deps (not in default APK build)

See [ANDROID_BUILD_GUIDE.md](ANDROID_BUILD_GUIDE.md) for build instructions.

## Verify

```bash
python -c "from main import UniversalSoulAI; print('import OK')"
python quick_test.py
```
