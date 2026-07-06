"""One-shot smoke test with live Ollama backend."""
import asyncio
import sys
from pathlib import Path

# UTF-8 console on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import UniversalSoulAI


async def run():
    print("Initializing Universal Soul AI with Ollama...")
    soul = UniversalSoulAI()
    await soul.initialize()

    status = await soul.get_system_status()
    hrm = status.get("hrm_engine", {})
    print(f"HRM backend: {hrm.get('model_type', hrm.get('backend_type', 'unknown'))}")
    print(f"ThinkMesh: {status['optimization_engines'].get('thinkmesh_enabled')}")
    print(f"Memory: {status['optimization_engines'].get('memory_enabled')}")
    print()

    prompt = "In one sentence, what is Universal Soul AI?"
    print(f"You: {prompt}")
    response = await soul.process_user_request(prompt, user_id="smoke_test")
    # Show a concise preview
    preview = response[:500] + ("..." if len(response) > 500 else "")
    print(f"\nAI: {preview}\n")

    await soul.shutdown()
    print("Smoke test complete — Ollama backend is live.")


if __name__ == "__main__":
    asyncio.run(run())
