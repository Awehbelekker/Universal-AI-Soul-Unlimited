#!/usr/bin/env python3
"""
System Performance Benchmark
Measures REAL runtime performance (latency, throughput, memory, CPU) of a
model inference function. Unlike accuracy benchmarks (MMLU/HellaSwag/ARC),
this focuses on how fast/efficient the model runs on the current device.

No simulated numbers: every metric is derived from actually calling the
provided async inference function.
"""

import asyncio
import time
import platform
import statistics
import threading
import queue
import logging
from typing import Callable, Awaitable, Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is in requirements.txt
    psutil = None

logger = logging.getLogger(__name__)


@dataclass
class SystemPerformanceResult:
    """Real runtime performance metrics for a model."""
    benchmark_name: str
    model_name: str
    num_iterations: int
    num_errors: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_req_per_sec: float
    peak_memory_mb: float
    avg_cpu_percent: float
    total_time_sec: float
    timestamp: str
    device_info: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """Background CPU/memory sampler using psutil (real measurements)."""

    def __init__(self, sample_interval_s: float = 0.1):
        self.sample_interval_s = sample_interval_s
        self._monitoring = False
        self._samples: "queue.Queue[Dict[str, float]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if psutil is None:
            return
        self._monitoring = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> Dict[str, float]:
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2.0)
        samples: List[Dict[str, float]] = []
        while not self._samples.empty():
            samples.append(self._samples.get())
        if not samples:
            return {"avg_cpu_percent": 0.0, "peak_memory_mb": 0.0}
        return {
            "avg_cpu_percent": statistics.mean(s["cpu"] for s in samples),
            "peak_memory_mb": max(s["memory"] for s in samples),
        }

    def _loop(self) -> None:
        while self._monitoring:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().used / (1024 * 1024)
                self._samples.put({"cpu": cpu, "memory": mem})
                time.sleep(self.sample_interval_s)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Monitoring error: %s", exc)


def _get_device_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }
    if psutil is not None:
        info["cpu_count"] = psutil.cpu_count()
        info["memory_gb"] = round(
            psutil.virtual_memory().total / (1024 ** 3), 2
        )
    return info


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


class SystemPerformanceBenchmark:
    """Measure real latency/throughput/memory/CPU of an inference function."""

    DEFAULT_PROMPTS = [
        "Summarize the benefits of local-first AI in one sentence.",
        "What is 17 multiplied by 23?",
        "List three uses for a hierarchical reasoning model.",
        "Explain what a personal AI companion does.",
        "Give a one-line privacy tip for mobile users.",
    ]

    def __init__(
        self,
        prompts: Optional[List[str]] = None,
        warmup: int = 1,
    ):
        self.prompts = prompts or self.DEFAULT_PROMPTS
        self.warmup = warmup

    async def run_benchmark(
        self,
        inference_fn: Callable[[str], Awaitable[str]],
        model_name: str,
    ) -> SystemPerformanceResult:
        """Run the inference function over prompts and measure real metrics."""
        logger.info("Running system performance benchmark on %s", model_name)

        # Warmup (not measured) to avoid cold-start skew.
        for _ in range(self.warmup):
            try:
                await inference_fn(self.prompts[0])
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Warmup call failed: %s", exc)

        monitor = PerformanceMonitor()
        monitor.start()

        latencies_ms: List[float] = []
        num_errors = 0
        run_start = time.perf_counter()

        for prompt in self.prompts:
            call_start = time.perf_counter()
            try:
                await inference_fn(prompt)
            except Exception as exc:
                num_errors += 1
                logger.error("Inference error: %s", exc)
                continue
            latencies_ms.append((time.perf_counter() - call_start) * 1000.0)

        total_time_sec = time.perf_counter() - run_start
        perf = monitor.stop()

        successful = len(latencies_ms)
        throughput = successful / total_time_sec if total_time_sec > 0 else 0.0

        return SystemPerformanceResult(
            benchmark_name="System Performance",
            model_name=model_name,
            num_iterations=len(self.prompts),
            num_errors=num_errors,
            latency_p50_ms=_percentile(latencies_ms, 50),
            latency_p95_ms=_percentile(latencies_ms, 95),
            latency_p99_ms=_percentile(latencies_ms, 99),
            avg_latency_ms=(
                statistics.mean(latencies_ms) if latencies_ms else 0.0
            ),
            min_latency_ms=min(latencies_ms) if latencies_ms else 0.0,
            max_latency_ms=max(latencies_ms) if latencies_ms else 0.0,
            throughput_req_per_sec=throughput,
            peak_memory_mb=perf.get("peak_memory_mb", 0.0),
            avg_cpu_percent=perf.get("avg_cpu_percent", 0.0),
            total_time_sec=total_time_sec,
            timestamp=datetime.now().isoformat(),
            device_info=_get_device_info(),
        )


def format_result(result: SystemPerformanceResult) -> str:
    """Human-readable summary of a system performance result."""
    return (
        f"\n{'=' * 60}\n"
        f"SYSTEM PERFORMANCE: {result.model_name}\n"
        f"{'=' * 60}\n"
        f"  Iterations:      {result.num_iterations} "
        f"({result.num_errors} errors)\n"
        f"  Latency p50:     {result.latency_p50_ms:.2f} ms\n"
        f"  Latency p95:     {result.latency_p95_ms:.2f} ms\n"
        f"  Latency p99:     {result.latency_p99_ms:.2f} ms\n"
        f"  Latency avg:     {result.avg_latency_ms:.2f} ms\n"
        f"  Throughput:      {result.throughput_req_per_sec:.2f} req/s\n"
        f"  Peak memory:     {result.peak_memory_mb:.1f} MB\n"
        f"  Avg CPU:         {result.avg_cpu_percent:.1f}%\n"
        f"  Total time:      {result.total_time_sec:.2f} s\n"
        f"{'=' * 60}"
    )


if __name__ == "__main__":
    import random

    async def _dummy(prompt: str) -> str:
        await asyncio.sleep(0.02 + random.random() * 0.03)
        return "ok"

    async def _main() -> None:
        logging.basicConfig(level=logging.INFO)
        bench = SystemPerformanceBenchmark()
        result = await bench.run_benchmark(_dummy, "dummy-model")
        print(format_result(result))

    asyncio.run(_main())
