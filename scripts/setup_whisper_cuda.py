#!/usr/bin/env python3
"""Install CUDA 12 runtime libs for faster-whisper GPU (Windows).

CTranslate2 (used by faster-whisper) needs cublas64_12.dll. PyTorch cu118
only ships cublas64_11.dll, and a full CUDA Toolkit is optional if you use
NVIDIA's pip wheels instead.

Usage:
  python scripts/setup_whisper_cuda.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PACKAGES = [
    "nvidia-cublas-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cuda-nvrtc-cu12",
    "nvidia-cufft-cu12",
    "nvidia-cuda-runtime-cu12",
]


def _nvidia_bin_dirs() -> list[str]:
    dirs: list[str] = []
    for modname in (
        "nvidia.cuda_runtime",
        "nvidia.cuda_nvrtc",
        "nvidia.cublas",
        "nvidia.cudnn",
        "nvidia.cufft",
    ):
        try:
            mod = __import__(modname, fromlist=["x"])
            root = Path(next(iter(mod.__path__)))
        except Exception:
            continue
        for cand in (root / "bin", root / "lib"):
            if cand.is_dir():
                dirs.append(str(cand))
    return dirs


def _prepend_user_path(dirs: list[str]) -> None:
    if os.name != "nt" or not dirs:
        return
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE,
        )
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
        parts = [p for p in current.split(";") if p]
        changed = False
        for d in reversed(dirs):
            if d not in parts:
                parts.insert(0, d)
                changed = True
        if changed:
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))
            print("Updated user PATH with NVIDIA pip bin dirs (new terminals pick this up).")
        else:
            print("User PATH already includes NVIDIA pip bin dirs.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Could not update user PATH (app still wires it at runtime): {e}")


def main() -> int:
    print("Installing NVIDIA CUDA 12 runtime wheels for faster-whisper…")
    cmd = [sys.executable, "-m", "pip", "install", *PACKAGES]
    subprocess.check_call(cmd)
    dirs = _nvidia_bin_dirs()
    if not dirs:
        print("ERROR: packages installed but no nvidia/*/bin dirs found.")
        return 1
    cublas = next(
        (
            Path(d) / "cublas64_12.dll"
            for d in dirs
            if (Path(d) / "cublas64_12.dll").is_file()
        ),
        None,
    )
    if cublas is None:
        print("ERROR: cublas64_12.dll not found after install.")
        return 1
    print(f"Found {cublas}")
    _prepend_user_path(dirs)

    # Smoke: load via DesktopVoiceService path wiring
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.voice_pipeline.desktop_voice import (  # noqa: E402
        DesktopVoiceService,
        _ensure_ctranslate2_cuda_dlls,
    )

    _ensure_ctranslate2_cuda_dlls()
    v = DesktopVoiceService(whisper_model="tiny")
    ok = v._ensure_whisper()
    print(f"Whisper ready: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
