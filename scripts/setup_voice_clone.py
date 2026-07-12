"""
Setup Coqui XTTS-v2 for local voice cloning.

Requires: NVIDIA GPU recommended (you have GTX 1080 Ti).
Installs PyTorch (CUDA 11.8) + Coqui TTS, then verifies XTTS loads.

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

    code = run([py, "-m", "pip", "install", "TTS"])
    if code != 0:
        print("Coqui TTS install failed.")
        return code

    print("\nVerifying import + CUDA…")
    verify = (
        "import torch; "
        "from TTS.api import TTS; "
        "print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); "
        "print('TTS import OK'); "
        "print('Next: in chat use  voice clone path\\to\\sample.wav'); "
        "print('Sample tip: 6-15s clean speech WAV, one speaker, no music.')"
    )
    return run([py, "-c", verify])


if __name__ == "__main__":
    raise SystemExit(main())
