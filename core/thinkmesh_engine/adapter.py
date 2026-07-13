"""
ThinkMesh Adapter (local thinkmesh_core + HRM fallback)
========================================================

Uses a real planner → critic → synthesizer multi-pass over HRM/Ollama when
deep routing asks for ThinkMesh. Optional external ``thinkmesh`` package and
local orchestrator remain available; simulated agent sleep is no longer the
product path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.config import get_config
from core.engines.hrm_engine import HRMEngine
from core.interfaces.data_structures import PersonalityMode, UserContext

logger = logging.getLogger(__name__)


@dataclass
class ThinkResult:
    content: str
    confidence: float
    meta: Dict[str, Any] = field(default_factory=dict)


class ThinkMeshAdapter:
    """Facade for ThinkMesh with real multi-pass reasoning + HRM fallback."""

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
        await self._hrm.initialize()

        # Prefer local thinkmesh_core orchestrator (with real executor)
        try:
            from thinkmesh_core.orchestration.orchestrator import (
                ThinkMeshOrchestrator,
            )

            self._orchestrator = ThinkMeshOrchestrator()
            await self._orchestrator.initialize()
            self._orchestrator.set_agent_executor(self._orchestrator_agent_run)
            await self._register_default_agents()
            self._uses_local_core = True
            self._available = True
        except Exception as e:
            logger.debug("thinkmesh_core orchestrator unavailable: %s", e)
            self._orchestrator = None
            self._uses_local_core = False

        # Optional external package
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

        # Multi-pass works whenever HRM is up
        self._available = True

    async def _register_default_agents(self) -> None:
        if not self._orchestrator:
            return
        defaults = (
            ("planner", ["planning", "reasoning"], {"performance_score": 0.7}),
            ("critic", ["analysis", "reasoning"], {"performance_score": 0.65}),
            (
                "synthesizer",
                ["synthesis", "reasoning"],
                {"performance_score": 0.75},
            ),
        )
        for agent_id, specs, caps in defaults:
            await self._orchestrator.register_agent(agent_id, specs, caps)

    async def _orchestrator_agent_run(
        self, agent_id: str, prompt: str, task: Any
    ) -> str:
        role_prompts = {
            "planner": (
                "You are a planner. List 3-6 concise angles or steps for "
                f"this task. No preamble.\n\nTask: {prompt}"
            ),
            "critic": (
                "You are a critic. List risks, gaps, or missing constraints "
                f"for this task. Bullets only.\n\nTask: {prompt}"
            ),
            "synthesizer": (
                "You are a synthesizer. Produce a short analysis that helps "
                f"answer the task.\n\nTask: {prompt}"
            ),
        }
        text = role_prompts.get(
            agent_id,
            f"Respond helpfully and briefly as agent '{agent_id}'.\n\n{prompt}",
        )
        return await self._hrm_brief(text, max_tokens=160)

    async def _hrm_brief(self, prompt: str, max_tokens: int = 180) -> str:
        ctx = UserContext(
            user_id="thinkmesh",
            session_id="thinkmesh-multipass",
            personality_mode=PersonalityMode.ANALYTICAL,
            values_profile=None,
        )
        text = await self._hrm.process_request(
            prompt,
            context=ctx,
            reasoning_depth=1,
            max_tokens=max_tokens,
        )
        return (text or "").strip()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def uses_local_core(self) -> bool:
        return self._uses_local_core

    async def think_multipass(self, task: str) -> ThinkResult:
        """Real planner → critic → synthesizer passes via HRM/Ollama."""
        steps: List[Dict[str, str]] = []

        plan = await self._hrm_brief(
            "You are a planner. List 3-6 concise angles or steps for this "
            f"task. Bullets only, no preamble.\n\nTask: {task}",
            max_tokens=160,
        )
        steps.append({"role": "planner", "content": plan})

        critique = await self._hrm_brief(
            "You are a critic. Given the task and plan, list risks, gaps, "
            "or missing constraints. Bullets only.\n\n"
            f"Task: {task}\n\nPlan:\n{plan}",
            max_tokens=160,
        )
        steps.append({"role": "critic", "content": critique})

        synthesis = await self._hrm_brief(
            "You are a synthesizer. Using the plan and critique, write a "
            "compact analysis (under 180 words) that helps answer the task. "
            "Do not repeat the plan verbatim.\n\n"
            f"Task: {task}\n\nPlan:\n{plan}\n\nCritique:\n{critique}",
            max_tokens=220,
        )
        steps.append({"role": "synthesizer", "content": synthesis})

        return ThinkResult(
            content=synthesis or plan,
            confidence=0.78,
            meta={
                "engine": "thinkmesh_multipass",
                "steps": steps,
                "local_core": self._uses_local_core,
            },
        )

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
        multipass: bool = True,
    ) -> ThinkResult:
        """Run thinking: multipass (product), external package, orchestrator, HRM."""
        # Product path first: real multi-pass over local HRM/Ollama
        if multipass:
            try:
                return await self.think_multipass(task)
            except Exception as e:
                logger.warning("ThinkMesh multipass failed: %s", e)

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
                import asyncio as _asyncio

                ans = self._think(task, cfg)
                if _asyncio.iscoroutine(ans):
                    ans = await ans
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
                    requirements={
                        "prompt": task,
                        "strategy": strategy or "adaptive",
                        "specializations": ["reasoning"],
                    },
                    context={"source": "thinkmesh_adapter"},
                    priority=TaskPriority.NORMAL,
                )
                active = self._orchestrator.active_tasks.get(task_id)
                if active:
                    await self._orchestrator._route_task(active)
                    result = active.result
                    if isinstance(result, dict) and result.get("content"):
                        return ThinkResult(
                            content=str(result["content"]),
                            confidence=0.7,
                            meta={
                                "engine": "thinkmesh_core",
                                "task_id": task_id,
                                "agent_id": result.get("agent_id"),
                            },
                        )
                    if result:
                        return ThinkResult(
                            content=str(result),
                            confidence=0.6,
                            meta={
                                "engine": "thinkmesh_core",
                                "task_id": task_id,
                            },
                        )
            except Exception as e:
                logger.debug("orchestrator path failed: %s", e)

        text = await self._hrm_brief(task, max_tokens=max_tokens or 256)
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
        if any(
            k in lw for k in ["step", "sequence", "simple", "list", "summarize"]
        ):
            return {"name": "SEQUENTIAL", "confidence": 0.6}
        return {"name": "ADAPTIVE", "confidence": 0.55}
