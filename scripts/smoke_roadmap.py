#!/usr/bin/env python3
"""Smoke: shared memory, family, offline pack, serve_pwa wiring."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from core.memory import shared_session
    from core.family import household
    from core.offline import light_pack
    from core.routing.task_router import TaskMode, classify_request

    shared_session.clear_session("smoke_session")
    assert shared_session.append_turn(
        "user", "hello smoke", session_id="smoke_session"
    )["ok"]
    assert shared_session.append_turn(
        "assistant", "hi back", session_id="smoke_session"
    )["ok"]
    turns = shared_session.recent_turns("smoke_session", limit=5)
    assert len(turns) == 2
    print("memory ok", len(turns))

    household.update_context(
        {
            "enabled": True,
            "name": "Smoke House",
            "shared_values": ["respect"],
            "boundaries": ["privacy"],
        }
    )
    household.upsert_member(
        {"display_name": "Sam", "role": "child", "pin": "99"}
    )
    assert household.verify_member("sam", "99")["ok"]
    assert not household.verify_member("sam", "00")["ok"]
    household.add_board_fact("Soccer Saturdays", member_id="primary")
    household.add_reminder("Pack lunch", member_id="primary", when="weekday")
    block = household.prompt_block("primary")
    assert "Smoke House" in block
    print("family ok")

    pack = light_pack.build_pack()
    assert pack["mode"] == "offline_light_pack"
    r = light_pack.light_reply("who are you", pack)
    assert r["ok"] and r["engine"] == "offline_light"
    light_pack.enqueue_sync("queued offline note")
    drained = light_pack.drain_queue()
    assert drained["count"] >= 1
    print("offline ok")

    route = classify_request("please analyze and synthesize a complex architecture strategy")
    assert route.mode == TaskMode.DEEP and route.use_thinkmesh
    print("routing ok", route.mode.value)

    path = ROOT / "scripts" / "serve_pwa.py"
    spec = importlib.util.spec_from_file_location("serve_pwa_smoke", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    for attr in (
        "_family_update",
        "_family_member",
        "_family_auth",
        "_offline_reply",
        "_chat",
    ):
        assert hasattr(mod.PWAHandler, attr), attr
    print("serve_pwa ok")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
