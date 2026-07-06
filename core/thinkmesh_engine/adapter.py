"""
ThinkMesh Adapter (local thinkmesh_core + HRM fallback)
========================================================

Uses the in-repo ``thinkmesh_core`` orchestrator when available, with
optional external ``thinkmesh`` package support. Falls back to HRM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.config import get_config
from core.engines.hrm_engine import HRMEngine


@dataclass
class ThinkResult:
    content: str
    confidence: float
    meta: Dict[str, Any]


class ThinkMeshAdapter:
    """Facade for ThinkMesh with HRM fallback."""

    def __init__(self) -> None:
        self._available = False
        self._uses_local_core = False
        self._hrm = HRMEngine()
        self._config = get_config()
        self._orchestrator = None

        # Optional external thinkmesh package
        self._ThinkConfig = None
        self._ModelSpec = None
        self._StrategySpec = None
        self._think = None

    async def initialize(self) -> None:
        # Prefer local thinkmesh_core orchestrator
        try:
            from thinkmesh_core.orchestration.orchestrator import (
                ThinkMeshOrchestrator,
            )
            self._orchestrator = ThinkMeshOrchestrator()
            await self._orchestrator.initialize()
            self._uses_local_core = True
            self._available = True
        except Exception:
            self._orchestrator = None
            self._uses_local_core = False

        # Optional external package (overrides if present)
        try:
            import importlib
            tm = importlib.import_module("thinkmesh")
            self._think = getattr(tm, "think")
            self._ThinkConfig = getattr(tm, "ThinkConfig")
            self._ModelSpec = getattr(tm, "ModelSpec")
            self._StrategySpec = getattr(tm, "StrategySpec")
            self._available = True
        except Exception:
            pass

        await self._hrm.initialize()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def uses_local_core(self) -> bool:
        return self._uses_local_core

    async def think(
        self,
        task: str,
        *,
        strategy: Optional[str] = None,
        parallel: Optional[int] = None,
        max_steps: Optional[int] = None,
        backend: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ThinkResult:
        """Run a thinking pass via external thinkmesh, local core, or HRM."""
        if (
            self._think
            and self._ThinkConfig
            and self._ModelSpec
            and self._StrategySpec
        ):
            backend = backend or "transformers"
            model_name = model_name or "Qwen2.5-7B-Instruct"
            max_tokens = max_tokens or 256
            temperature = temperature if temperature is not None else 0.7
            strategy = strategy or "deepconf"
            parallel = parallel or 6
            max_steps = max_steps or 2

            cfg = self._ThinkConfig(
                model=self._ModelSpec(
                    backend=backend,
                    model_name=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra={"device": "auto"},
                ),
                strategy=self._StrategySpec(
                    name=strategy,
                    parallel=parallel,
                    max_steps=max_steps,
                ),
                reducer={"name": "majority"},
                budgets={"wall_clock_s": 20, "tokens": 4000},
            )
            try:
                ans = self._think(task, cfg)
                return ThinkResult(
                    content=ans.content,
                    confidence=float(ans.confidence),
                    meta=ans.meta,
                )
            except Exception:
                pass

        if self._orchestrator:
            try:
                from thinkmesh_core.orchestration.orchestrator import (
                    TaskPriority,
                )
                task_id = await self._orchestrator.submit_task(
                    task_type="reasoning",
                    requirements={"prompt": task, "strategy": strategy or "adaptive"},
                    context={"source": "thinkmesh_adapter"},
                    priority=TaskPriority.NORMAL,
                )
                # Route synchronously for adapter callers
                active = self._orchestrator.active_tasks.get(task_id)
                if active:
                    await self._orchestrator._route_task(active)
                    result = active.result
                    if result:
                        return ThinkResult(
                            content=str(result),
                            confidence=0.65,
                            meta={"engine": "thinkmesh_core", "task_id": task_id},
                        )
            except Exception:
                pass

        from core.interfaces.data_structures import UserContext, PersonalityMode

        ctx = UserContext(
            user_id="system",
            session_id="thinkmesh-fallback",
            personality_mode=PersonalityMode.FRIENDLY,
            values_profile=None,
        )
        text = await self._hrm.process_request(task, context=ctx)
        return ThinkResult(
            content=text,
            confidence=0.5,
            meta={"engine": "hrm_fallback"},
        )

    async def recommend_strategy(self, text: str) -> Dict[str, Any]:
        """Lightweight strategy recommendation from task text."""
        lw = text.lower()
        if any(
            k in lw
            for k in ["prove", "synthesize", "plan", "orchestrate", "complex"]
        ):
            return {"name": "HYBRID", "confidence": 0.7}
        if any(k in lw for k in ["compare", "debate", "tradeoff", "versus"]):
            return {"name": "PARALLEL", "confidence": 0.65}
        if any(k in lw for k in ["step", "sequence", "simple", "list", "summarize"]):
            return {"name": "SEQUENTIAL", "confidence": 0.6}
        return {"name": "ADAPTIVE", "confidence": 0.55}
