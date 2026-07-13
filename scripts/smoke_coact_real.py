#!/usr/bin/env python3
"""Smoke-test real CoAct allowlisted actions (consent + audit)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.automation.real_actions import (  # noqa: E402
    AUDIT_LOG,
    SANDBOX_DIR,
    execute_real_action,
    parse_action,
    read_audit,
)
from core.engines.coact_engine import CoAct1AutomationEngine  # noqa: E402
from core.interfaces.data_structures import AutomationTask  # noqa: E402


def _run(desc: str, consent: bool = True):
    parsed = parse_action(desc)
    assert parsed is not None, f"parse failed: {desc}"
    return execute_real_action(
        parsed, consent=consent, source="smoke", description=desc
    )


def test_direct() -> None:
    blocked = _run("note hello without consent", consent=False)
    assert blocked["success"] is False, blocked
    assert "Consent" in (blocked.get("error_message") or "")

    ok = _run("note CoAct smoke note")
    assert ok["success"] is True, ok
    path = Path(ok["detail"]["path"])
    assert path.is_file()

    listed = _run("list")
    assert listed["success"] is True, listed
    assert listed["detail"]["count"] >= 1

    info = _run("info")
    assert info["success"] is True, info
    assert "sandbox" in info["detail"]

    read = _run(f"read {path.name}")
    assert read["success"] is True, read
    assert "CoAct smoke note" in read["detail"]["text"]

    mkdir = _run("mkdir smoke_dir")
    assert mkdir["success"] is True, mkdir

    append = _run(f"append {path.name} second line")
    assert append["success"] is True, append
    assert "second line" in path.read_text(encoding="utf-8")

    copy = _run(f"copy {path.name} smoke_copy.txt")
    assert copy["success"] is True, copy
    assert (SANDBOX_DIR / "smoke_copy.txt").is_file()

    # Outside allowlist must fail
    bad = _run("open C:/Windows")
    assert bad["success"] is False, bad

    # Delete outside sandbox must fail
    bad_del = _run("delete ../user_profiles")
    assert bad_del["success"] is False, bad_del

    deleted = _run("delete smoke_copy.txt")
    assert deleted["success"] is True, deleted

    empty = _run("delete smoke_dir")
    assert empty["success"] is True, empty

    entries = read_audit(10)
    assert entries, "expected audit log entries"
    assert AUDIT_LOG.is_file()
    print("direct OK — expanded allowlist + audit")


async def test_engine() -> None:
    engine = CoAct1AutomationEngine()
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
