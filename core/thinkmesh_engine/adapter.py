"""
ThinkMesh Adapter (with graceful HRM fallback)
=============================================

This module provides a minimal integration surface for ThinkMesh.
If the `thinkmesh` package is available, it will be used to run parallel
reasoning. If not, it falls back to the local HRM engine to ensure
the rest of the system can proceed without runtime errors.
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
    """Facade for ThinkMesh with HRM fallback.

    Public contract:
    - initialize(): probe availability and warm up fallback
        - think(task: str, *, strategy: str|None, parallel: int|None,
            max_steps: int|None) -> ThinkResult
    - recommend_strategy(text: str) -> Dict[str, Any]
    """

    def __init__(self) -> None:
        self._available = False
        self._hrm = HRMEngine()
        self._config = get_config()

        # ThinkMesh symbols (late-bound)
        self._ThinkConfig = None
        self._ModelSpec = None
        self._StrategySpec = None
        self._think = None

    async def initialize(self) -> None:
        # Try import thinkmesh; if not present, remain in HRM fallback mode
        try:
            import importlib
            tm = importlib.import_module("thinkmesh")
            self._think = getattr(tm, "think")
            self._ThinkConfig = getattr(tm, "ThinkConfig")
            self._ModelSpec = getattr(tm, "ModelSpec")
            self._StrategySpec = getattr(tm, "StrategySpec")
            self._available = True
        except Exception:
            self._available = False

        # Initialize fallback HRM regardless so we can use it immediately
        await self._hrm.initialize()

    @property
    def available(self) -> bool:
        return self._available

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
        """Run a thinking pass.

        If ThinkMesh is available, use its orchestrator; otherwise use HRM.
        """
        if (
            self._available
            and self._think
            and self._ThinkConfig
            and self._ModelSpec
            and self._StrategySpec
        ):
            # Build a ThinkMesh config with sensible defaults for local usage
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
                # If ThinkMesh runtime fails, fall back to HRM for resilience
                pass

        # Fallback: use HRM hierarchical reasoning
        from core.interfaces.data_structures import (
            UserContext,
            PersonalityMode,
        )

        ctx = UserContext(
            user_id="system",
            session_id="thinkmesh-fallback",
            personality_mode=PersonalityMode.FRIENDLY,
            values_profile=None,
        )
        text = await self._hrm.process_request(task, context=ctx)
        # HRM does not output numeric confidence; return a neutral value
        return ThinkResult(
            content=text,
            confidence=0.5,
            meta={"engine": "hrm_fallback"},
        )

    async def recommend_strategy(self, text: str) -> Dict[str, Any]:
        """Provide a lightweight strategy recommendation from text.

    Uses a simple heuristic today; when ThinkMesh is available we could
    route through a cheap pass (e.g., self_consistency) to estimate
    difficulty.
        """
        lw = text.lower()
        if any(
            k in lw
            for k in [
                "prove",
                "synthesize",
                "plan",
                "orchestrate",
                "multiple",
                "complex",
            ]
        ):
            return {"name": "HYBRID", "confidence": 0.7}
        if any(k in lw for k in ["compare", "debate", "tradeoff", "versus"]):
            return {"name": "PARALLEL", "confidence": 0.65}
        if any(
            k in lw
            for k in [
                "step",
                "sequence",
                "simple",
                "list",
                "summarize",
            ]
        ):
            return {"name": "SEQUENTIAL", "confidence": 0.6}
        return {"name": "ADAPTIVE", "confidence": 0.55}
