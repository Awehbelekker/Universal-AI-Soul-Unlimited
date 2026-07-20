"""
ThinkMesh Adapter
=================

Product path for deep reasoning:
  1. External ``thinkmesh`` package (DeepConf / debate / self_consistency / tree)
     via Ollama — preferred when installed
  2. Local planner → critic → synthesizer multipass over HRM/Ollama — fallback
  3. thinkmesh_core orchestrator / HRM brief — last resort
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core.config import get_config
from core.engines.hrm_engine import HRMEngine
from core.interfaces.data_structures import PersonalityMode, UserContext

logger = logging.getLogger(__name__)

_STRATEGY_NAMES = frozenset(
    {"deepconf", "debate", "self_consistency", "tree", "graph"}
)


@dataclass
class ThinkResult:
    content: str
    confidence: float
    meta: Dict[str, Any] = field(default_factory=dict)


def map_strategy_name(text: str) -> str:
    """Map task text to a real ThinkMesh strategy name."""
    lw = (text or "").lower()
    if any(k in lw for k in ("compare", "debate", "tradeoff", "versus", "vs ", " or ")):
        return "debate"
    if any(
        k in lw
        for k in ("prove", "architect", "multi-step", "orchestrate", "design system")
    ):
        return "tree"
    if any(k in lw for k in ("analyze", "evaluate", "synthesize", "complex", "think about")):
        return "deepconf"
    return "self_consistency"


class ThinkMeshAdapter:
    """Facade: real ThinkMesh strategies first, multipass/HRM fallback."""

    def __init__(self) -> None:
        self._available = False
        self._uses_local_core = False
        self._uses_package = False
        self._hrm = HRMEngine()
        self._config = get_config()
        self._orchestrator = None

        self._ThinkConfig = None
        self._ModelSpec = None
        self._StrategySpec = None
        self._think = None

    async def initialize(self) -> None:
        await self._hrm.initialize()

        # Prefer external ThinkMesh package (Desktop install)
        try:
            import importlib

            tm = importlib.import_module("thinkmesh")
            self._think = getattr(tm, "think")
            self._ThinkConfig = getattr(tm, "ThinkConfig")
            self._ModelSpec = getattr(tm, "ModelSpec")
            self._StrategySpec = getattr(tm, "StrategySpec")
            self._uses_package = True
            self._available = True
            logger.info("ThinkMesh package available (Ollama strategies enabled)")
        except Exception as e:
            logger.debug("thinkmesh package unavailable: %s", e)
            self._uses_package = False

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

        # Multipass always works when HRM is up
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

    @property
    def uses_package(self) -> bool:
        return self._uses_package

    def _default_ollama_base(self) -> str:
        raw = (
            getattr(self._config, "ollama_url", None)
            or getattr(getattr(self._config, "hrm", None), "ollama_url", None)
            or "http://127.0.0.1:11434"
        )
        u = str(raw).rstrip("/")
        if u.endswith("/v1"):
            return u
        # ThinkMesh Ollama adapter expects OpenAI-compatible /v1 base
        parsed = urlparse(u if "://" in u else f"http://{u}")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        return f"http://{host}:{port}/v1"

    def _default_model_name(self) -> str:
        for attr in ("ollama_model", "default_model", "model"):
            val = getattr(self._config, attr, None)
            if val:
                return str(val)
        hrm = getattr(self._config, "hrm", None)
        if hrm is not None:
            for attr in ("model", "ollama_model"):
                val = getattr(hrm, attr, None)
                if val:
                    return str(val)
        return "llama3.2:3b"

    async def think_multipass(self, task: str) -> ThinkResult:
        """Planner → critic → synthesizer via HRM/Ollama (fallback path)."""
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

    async def think_package(
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
        ollama_base_url: Optional[str] = None,
    ) -> ThinkResult:
        """Run a real ThinkMesh strategy (DeepConf / debate / SC / tree)."""
        if not (
            self._think
            and self._ThinkConfig
            and self._ModelSpec
            and self._StrategySpec
        ):
            raise RuntimeError("thinkmesh package not loaded")

        backend = backend or "ollama"
        model_name = model_name or self._default_model_name()
        max_tokens = max_tokens or 256
        temperature = 0.6 if temperature is None else temperature
        raw_strategy = (strategy or map_strategy_name(task)).strip().lower()
        if raw_strategy not in _STRATEGY_NAMES:
            raw_strategy = map_strategy_name(task)
        # Keep PWA deep path snappy on small local models
        if parallel is None:
            parallel = 3 if raw_strategy in ("self_consistency", "deepconf") else 2
        max_steps = max_steps or (2 if raw_strategy in ("deepconf", "debate", "tree") else 1)

        extra: Dict[str, Any] = {"batch_size": min(parallel, 4)}
        if backend == "ollama":
            extra["base_url"] = ollama_base_url or self._default_ollama_base()
            extra["use_thinking"] = False  # small chat models; avoid think token burn
        elif backend == "transformers":
            extra["device"] = "auto"

        strategy_kwargs: Dict[str, Any] = {
            "name": raw_strategy,
            "parallel": parallel,
            "max_steps": max_steps,
        }
        if raw_strategy == "deepconf":
            strategy_kwargs["deepconf"] = {
                "k": min(5, parallel),
                "tau_low": -1.25,
                "tau_ent": 2.2,
                "realloc_top_p": 0.4,
            }
        elif raw_strategy == "debate":
            strategy_kwargs["debate"] = {"rounds": 2}
        elif raw_strategy == "tree":
            strategy_kwargs["tree"] = {"branches": 2, "depth": 2}

        cfg = self._ThinkConfig(
            model=self._ModelSpec(
                backend=backend,
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                extra=extra,
            ),
            strategy=self._StrategySpec(**strategy_kwargs),
            reducer={"name": "majority"},
            budgets={"wall_clock_s": 45, "tokens": 3500},
        )

        import asyncio as _asyncio

        # thinkmesh.think() wraps Orchestrator.run in asyncio.run(), which
        # fails when we are already inside an event loop — call run() directly.
        try:
            from thinkmesh.orchestrator import Orchestrator
        except ImportError:
            Orchestrator = None  # type: ignore

        if Orchestrator is not None:
            ans = await Orchestrator(cfg).run(task)
        else:
            ans = self._think(task, cfg)
            if _asyncio.iscoroutine(ans):
                ans = await ans
        meta = dict(getattr(ans, "meta", None) or {})
        meta.update(
            {
                "engine": "thinkmesh_package",
                "strategy": raw_strategy,
                "backend": backend,
                "model": model_name,
            }
        )
        return ThinkResult(
            content=(getattr(ans, "content", None) or str(ans) or "").strip(),
            confidence=float(getattr(ans, "confidence", 0.7) or 0.7),
            meta=meta,
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
        multipass: bool = False,
        ollama_base_url: Optional[str] = None,
        prefer_package: bool = True,
    ) -> ThinkResult:
        """Run thinking: package strategies → multipass → orchestrator → HRM."""
        # 1) Real ThinkMesh strategies (preferred)
        if prefer_package and self._uses_package and not multipass:
            try:
                return await self.think_package(
                    task,
                    strategy=strategy,
                    parallel=parallel,
                    max_steps=max_steps,
                    backend=backend or "ollama",
                    model_name=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    ollama_base_url=ollama_base_url,
                )
            except Exception as e:
                logger.warning("ThinkMesh package path failed: %s", e)

        # 2) Multipass fallback (or explicit multipass=True)
        if multipass or prefer_package:
            try:
                return await self.think_multipass(task)
            except Exception as e:
                logger.warning("ThinkMesh multipass failed: %s", e)

        # 3) Retry package if multipass was forced first and failed
        if prefer_package and self._uses_package and multipass:
            try:
                return await self.think_package(
                    task,
                    strategy=strategy,
                    parallel=parallel,
                    max_steps=max_steps,
                    backend=backend or "ollama",
                    model_name=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    ollama_base_url=ollama_base_url,
                )
            except Exception as e:
                logger.debug("package after multipass also failed: %s", e)

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
        """Recommend a real ThinkMesh strategy name for the task."""
        name = map_strategy_name(text)
        conf = 0.7 if name != "self_consistency" else 0.6
        return {"name": name, "confidence": conf, "engine": "thinkmesh"}
