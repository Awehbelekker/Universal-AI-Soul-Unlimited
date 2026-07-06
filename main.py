"""
Universal Soul AI - Entry Point
===============================

- Imports ``UniversalSoulAI`` from the desktop orchestrator for library use.
- On Android: launches the Kivy UI (``app_main``).
- On desktop: runs the full async CLI (``main_desktop``).
"""

from __future__ import annotations

import sys

from main_desktop import UniversalSoulAI

__all__ = ["UniversalSoulAI"]


def _is_android() -> bool:
    try:
        from jnius import autoclass
        autoclass("org.kivy.android.PythonActivity")
        return True
    except Exception:
        return "android" in sys.platform.lower()


def main() -> None:
    if _is_android():
        from app_main import main as android_main
        android_main()
    else:
        import asyncio
        from main_desktop import main as desktop_main
        asyncio.run(desktop_main())


if __name__ == "__main__":
    main()
