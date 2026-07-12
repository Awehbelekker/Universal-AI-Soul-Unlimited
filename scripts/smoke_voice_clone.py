"""
Smoke-test XTTS cloning: build an Edge demo sample, then synthesize one line.

Usage:
  python scripts/smoke_voice_clone.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def main() -> int:
    # XTTS CPML non-commercial ack (https://coqui.ai/cpml)
    os.environ.setdefault("COQUI_TOS_AGREED", "1")

    from core.voice_pipeline.desktop_voice import DesktopVoiceService

    voice = DesktopVoiceService()
    await voice.initialize()
    print("coqui_available:", voice._coqui_available)
    print("Building demo sample…")
    msg = await voice.make_edge_demo_sample()
    print(msg)
    if not voice.clone_wav:
        return 1

    print("Loading XTTS (first run may download the model)…")
    ok = await voice._ensure_coqui_xtts()
    if not ok:
        print("XTTS failed to initialize.")
        return 1

    print("Speaking clone sample…")
    spoken = await voice.speak(
        "Universal Soul can clone a voice from a short sample.",
        personality="friendly",
    )
    print("speak ok:", spoken)
    print("status:", voice.status())
    return 0 if spoken else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
