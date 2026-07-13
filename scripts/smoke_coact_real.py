#!/usr/bin/env python3
"""Smoke-test real CoAct allowlisted actions (consent + audit)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.automation.real_actions import (  # noqa: E402
    AUDIT_LOG,
    execute_real_action,
    parse_action,
    read_audit,
)
from core.engines.coact_engine import CoAct1AutomationEngine  # noqa: E402
from core.interfaces.data_structures import AutomationTask  # noqa: E402
import asyncio


def test_direct() -> None:
    blocked = execute_real_action(
        parse_action("note hello without consent"),
        consent=False,
        source="smoke",
        description="note hello without consent",
    )
    assert blocked["success"] is False, blocked
    assert "Consent" in (blocked.get("error_message") or "")

    ok = execute_real_action(
        parse_action("note CoAct smoke note"),
        consent=True,
        source="smoke",
        description="note CoAct smoke note",
    )
    assert ok["success"] is True, ok
    path = Path(ok["detail"]["path"])
    assert path.is_file()
    assert "CoAct smoke note" in path.read_text(encoding="utf-8")

    listed = execute_real_action(
        parse_action("list"),
        consent=True,
        source="smoke",
        description="list",
    )
    assert listed["success"] is True, listed
    assert listed["detail"]["count"] >= 1

    # Outside allowlist must fail
    bad = execute_real_action(
        parse_action("open C:/Windows"),
        consent=True,
        source="smoke",
        description="open C:/Windows",
    )
    assert bad["success"] is False, bad

    entries = read_audit(10)
    assert entries, "expected audit log entries"
    assert AUDIT_LOG.is_file()
    print("direct OK — note/list/deny + audit")


async def test_engine() -> None:
    engine = CoAct1AutomationEngine()
    # Skip full initialize (background loop); call execute which inits
    # But initialize starts background forever — use execute_real via execute_task
    # after minimal init of strategies only
    await engine._initialize_strategies()
    engine.is_initialized = True

    task = AutomationTask(description="note engine path works", task_type="smoke")
    result = await engine.execute_task(task, {"consent": True})
    assert result.get("real") is True, result
    assert result.get("success") is True, result
    print("engine OK —", result.get("detail"))


def main() -> int:
    test_direct()
    asyncio.run(test_engine())
    print("smoke_coact_real: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
