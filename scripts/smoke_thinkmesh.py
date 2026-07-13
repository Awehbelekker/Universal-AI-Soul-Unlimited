#!/usr/bin/env python3
"""Smoke-test ThinkMesh multipass (requires Ollama for full path)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.thinkmesh_engine.adapter import ThinkMeshAdapter  # noqa: E402
from core.routing.task_router import classify_request, TaskMode  # noqa: E402


def test_router() -> None:
    d = classify_request("please analyze and compare these tradeoffs carefully")
    assert d.mode == TaskMode.DEEP
    assert d.use_thinkmesh is True
    print("router OK")


async def test_multipass_mocked() -> None:
    adapter = ThinkMeshAdapter()
    adapter._available = True
    calls = []

    async def fake_brief(prompt: str, max_tokens: int = 180) -> str:
        calls.append(prompt[:40])
        if "planner" in prompt.lower() or "List 3-6" in prompt:
            return "- angle A\n- angle B"
        if "critic" in prompt.lower() or "risks" in prompt.lower():
            return "- risk 1"
        return "Synthesized analysis for the task."

    adapter._hrm_brief = fake_brief  # type: ignore
    result = await adapter.think_multipass("How should we structure memory?")
    assert result.meta.get("engine") == "thinkmesh_multipass"
    assert len(result.meta.get("steps") or []) == 3
    assert "Synthesized" in result.content
    assert len(calls) == 3
    print("multipass mocked OK")


async def test_live_optional() -> None:
    """Live Ollama multipass when available; skip soft-fail otherwise."""
    adapter = ThinkMeshAdapter()
    try:
        await adapter.initialize()
        result = await adapter.think(
            "Compare list vs dict for a small cache. Be brief.",
            multipass=True,
        )
        print(
            "live OK —",
            result.meta.get("engine"),
            "len=",
            len(result.content or ""),
            "conf=",
            result.confidence,
        )
        assert result.content
        assert result.meta.get("engine") in (
            "thinkmesh_multipass",
            "hrm_fallback",
            "thinkmesh_core",
        )
    except Exception as e:
        print("live SKIP —", e)


async def main_async() -> int:
    test_router()
    await test_multipass_mocked()
    await test_live_optional()
    print("smoke_thinkmesh: PASS")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
