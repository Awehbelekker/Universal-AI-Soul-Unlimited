"""
Setup Coqui XTTS-v2 for local voice cloning.

Requires: NVIDIA GPU recommended (you have GTX 1080 Ti).
Installs PyTorch (CUDA 11.8) + coqui-tts (maintained fork with Windows wheels).

Do NOT use `pip install TTS` on Windows — that old package builds from source and
needs Microsoft C++ Build Tools. Use `coqui-tts` instead (same `TTS` import path).

Usage:
  python scripts/setup_voice_clone.py
  python scripts/setup_voice_clone.py --cpu   # slower, no CUDA
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print(">", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install XTTS voice cloning stack")
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Install CPU-only PyTorch (much slower for cloning)",
    )
    args = parser.parse_args()

    py = sys.executable

    if args.cpu:
        code = run([py, "-m", "pip", "install", "torch", "torchaudio"])
    else:
        code = run(
            [
                py,
                "-m",
                "pip",
                "install",
                "torch",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/cu118",
            ]
        )
    if code != 0:
        print("PyTorch install failed.")
        return code

    # Remove deprecated Coqui package if present (conflicts with coqui-tts).
    run([py, "-m", "pip", "uninstall", "-y", "TTS"])

    code = run([py, "-m", "pip", "install", "coqui-tts", "transformers>=4.57,<5"])
    if code != 0:
        print(
            "coqui-tts install failed.\n"
            "If you see a C++ / Visual Studio build error, install Build Tools with "
            "the 'Desktop development with C++' workload:\n"
            "  https://visualstudio.microsoft.com/visual-cpp-build-tools/\n"
            "Or: winget install Microsoft.VisualStudio.2022.BuildTools "
            "--override \"--wait --passive --add Microsoft.VisualStudio.Workload.VCTools "
            "--includeRecommended\""
        )
        return code

    print("\nVerifying import + CUDA…")
    verify = (
        "import torch; "
        "from TTS.api import TTS; "
        "print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); "
        "print('TTS import OK'); "
        "print('Next: in chat use  voice clone path\\\\to\\\\sample.wav'); "
        "print('Sample tip: 6-15s clean speech WAV, one speaker, no music.')"
    )
    return run([py, "-c", verify])


if __name__ == "__main__":
    raise SystemExit(main())
