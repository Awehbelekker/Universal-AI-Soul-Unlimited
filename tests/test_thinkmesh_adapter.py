"""ThinkMesh adapter strategy mapping + package preference."""

import asyncio

from core.thinkmesh_engine.adapter import ThinkMeshAdapter, map_strategy_name


def test_map_strategy_debate():
    assert map_strategy_name("compare Argentina vs France") == "debate"


def test_map_strategy_deepconf():
    assert map_strategy_name("analyze the trade-offs carefully") == "deepconf"


def test_map_strategy_tree():
    assert map_strategy_name("prove and architect a multi-step design system") == "tree"


def test_map_strategy_default_sc():
    assert map_strategy_name("help me think this through briefly") in (
        "self_consistency",
        "deepconf",
    )


def test_recommend_strategy_returns_package_names():
    adapter = ThinkMeshAdapter()

    async def _run():
        return await adapter.recommend_strategy(
            "prove that sqrt(2) is irrational"
        )

    rec = asyncio.run(_run())
    assert rec["name"] in {
        "tree",
        "deepconf",
        "self_consistency",
        "debate",
        "graph",
    }


def test_adapter_loads_package():
    async def _run():
        adapter = ThinkMeshAdapter()
        await adapter.initialize()
        return adapter.uses_package

    assert asyncio.run(_run()) is True
