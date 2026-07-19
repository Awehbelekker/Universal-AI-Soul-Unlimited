#!/usr/bin/env python3
"""Smoke: wow tools catalog + local tools (no network required for calc/uuid)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from core.integrations import wow_tools

    cat = wow_tools.catalog()
    assert cat["ok"] and len(cat["tools"]) >= 8
    print("tools:", len(cat["tools"]), "search=", cat.get("search_provider"))

    calc = wow_tools.run_tool("calc", {"expression": "2+2*3"})
    assert calc["ok"] and calc.get("value") == 8, calc
    print("calc ok:", calc["summary"])

    uid = wow_tools.run_tool("uuid", {})
    assert uid["ok"] and len(uid.get("value") or "") > 10
    print("uuid ok")

    intent = wow_tools.detect_intent("weather in Cape Town")
    assert intent and intent[0] == "weather"
    print("intent ok:", intent)

    intent2 = wow_tools.detect_intent("search quantum computing")
    assert intent2 and intent2[0] == "web_search"
    print("search intent ok")

    path = ROOT / "scripts" / "serve_pwa.py"
    spec = importlib.util.spec_from_file_location("serve_pwa_smoke", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    assert hasattr(mod.PWAHandler, "_chat")
    assert hasattr(mod.PWAHandler, "_tools_run")
    print("serve_pwa routes ok")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
