"""
Adaptive task routing — fast chat vs standard vs deep reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskMode(Enum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class RouteDecision:
    mode: TaskMode
    reasoning_depth: int
    max_tokens: int
    use_automation: bool
    use_thinkmesh: bool


_AUTOMATION_KEYWORDS = (
    "automate", "schedule", "remind", "execute", "perform",
    "run", "launch", "build", "implement", "deploy",
)

_DEEP_KEYWORDS = (
    "prove", "analyze", "architect", "design", "refactor",
    "optimize", "compare", "evaluate", "synthesize", "debug",
    "multi-step", "complex", "orchestrate", "strategy",
)

_STANDARD_KEYWORDS = (
    "explain", "help me", "how do", "what is", "why does",
    "plan", "summarize", "outline",
)

_MEMORY_KEYWORDS = ("remember", "don't forget", "note that", "keep in mind")


def classify_request(
    text: str,
    *,
    has_memory_context: bool = False,
    adaptive: bool = True,
    default_depth: int = 1,
    max_depth: int = 3,
    fast_tokens: int = 256,
    deep_tokens: int = 512,
) -> RouteDecision:
    """Pick inference mode from message content and complexity."""
    if not adaptive:
        return RouteDecision(
            mode=TaskMode.FAST,
            reasoning_depth=default_depth,
            max_tokens=fast_tokens,
            use_automation=False,
            use_thinkmesh=False,
        )

    lw = text.lower().strip()
    words = lw.split()
    word_count = len(words)

    if any(k in lw for k in _MEMORY_KEYWORDS) and word_count < 25:
        return RouteDecision(
            mode=TaskMode.FAST,
            reasoning_depth=1,
            max_tokens=128,
            use_automation=False,
            use_thinkmesh=False,
        )

    if word_count <= 12 and not any(k in lw for k in _DEEP_KEYWORDS):
        return RouteDecision(
            mode=TaskMode.FAST,
            reasoning_depth=1,
            max_tokens=fast_tokens,
            use_automation=False,
            use_thinkmesh=False,
        )

    if any(k in lw for k in _DEEP_KEYWORDS) or word_count > 100:
        return RouteDecision(
            mode=TaskMode.DEEP,
            reasoning_depth=max_depth,
            max_tokens=deep_tokens,
            use_automation=True,
            use_thinkmesh=True,
        )

    if any(k in lw for k in _AUTOMATION_KEYWORDS):
        return RouteDecision(
            mode=TaskMode.STANDARD,
            reasoning_depth=min(2, max_depth),
            max_tokens=fast_tokens,
            use_automation=True,
            use_thinkmesh=False,
        )

    if any(k in lw for k in _STANDARD_KEYWORDS) or has_memory_context:
        return RouteDecision(
            mode=TaskMode.STANDARD,
            reasoning_depth=min(2, max_depth),
            max_tokens=fast_tokens,
            use_automation=False,
            use_thinkmesh=False,
        )

    return RouteDecision(
        mode=TaskMode.FAST,
        reasoning_depth=1,
        max_tokens=fast_tokens,
        use_automation=False,
        use_thinkmesh=False,
    )
