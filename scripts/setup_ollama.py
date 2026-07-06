#!/usr/bin/env python3
"""
Setup runtime dependencies for Universal Soul AI (Ollama + Qwen2.5-3B).

Model weights are NOT shipped in this repository. This script verifies
Ollama is installed and pulls the default model.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "universal_soul.json"
DEFAULT_MODEL = "qwen2.5:3b"
OLLAMA_URL = "http://localhost:11434"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"hrm": {"ollama_model": DEFAULT_MODEL, "ollama_url": OLLAMA_URL}}


def ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def ollama_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def run_ollama(args: list[str]) -> bool:
    try:
        subprocess.run(["ollama", *args], check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  Error: {exc}")
        return False


def main() -> int:
    config = load_config()
    hrm = config.get("hrm", {})
    model = hrm.get("ollama_model", DEFAULT_MODEL)
    url = hrm.get("ollama_url", OLLAMA_URL)

    print("=" * 60)
    print("Universal Soul AI — Runtime Setup (Ollama)")
    print("=" * 60)

    if not ollama_installed():
        print("\nOllama is not installed.")
        print("  Windows: https://ollama.com/download")
        print("  Linux:   curl -fsSL https://ollama.com/install.sh | sh")
        print("\nAfter installing, re-run: python scripts/setup_ollama.py")
        return 1

    print("\n[OK] Ollama CLI found")

    if not ollama_running(url):
        print(f"\nOllama server not reachable at {url}")
        print("  Start Ollama (it usually runs as a background service).")
        print("  Then re-run this script.")
        return 1

    print(f"[OK] Ollama server running at {url}")

    print(f"\nPulling model: {model}")
    if not run_ollama(["pull", model]):
        return 1

    print(f"\n[OK] Model '{model}' ready")
    print("\nNext steps:")
    print("  python main_desktop.py")
    print("  python quick_test.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
