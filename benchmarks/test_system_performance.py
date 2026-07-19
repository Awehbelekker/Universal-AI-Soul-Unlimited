"""
Unit tests for the system performance benchmark.

Validates that real metrics are computed correctly from a controlled dummy
inference function (no external models or network required).
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Make the benchmarks directory importable regardless of pytest rootdir.
sys.path.insert(0, str(Path(__file__).parent))

from system_performance_benchmark import (  # noqa: E402
    SystemPerformanceBenchmark,
    SystemPerformanceResult,
    _percentile,
    format_result,
)


def test_percentile_basic():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 50) == 30.0
    assert _percentile(values, 0) == 10.0
    assert _percentile(values, 100) == 50.0


def test_percentile_empty():
    assert _percentile([], 95) == 0.0


@pytest.mark.asyncio
async def test_run_benchmark_structure():
    async def dummy(prompt: str) -> str:
        await asyncio.sleep(0.01)
        return "ok"

    prompts = ["a", "b", "c", "d"]
    bench = SystemPerformanceBenchmark(prompts=prompts, warmup=1)
    result = await bench.run_benchmark(dummy, "dummy-model")

    assert isinstance(result, SystemPerformanceResult)
    assert result.model_name == "dummy-model"
    assert result.num_iterations == len(prompts)
    assert result.num_errors == 0
    # Each dummy call sleeps ~10ms, so latency should be measurable/positive.
    assert result.avg_latency_ms > 0
    assert result.latency_p50_ms > 0
    assert result.throughput_req_per_sec > 0
    assert result.min_latency_ms <= result.avg_latency_ms <= result.max_latency_ms
    assert "platform" in result.device_info


@pytest.mark.asyncio
async def test_run_benchmark_counts_errors():
    async def flaky(prompt: str) -> str:
        if prompt == "boom":
            raise RuntimeError("simulated failure")
        await asyncio.sleep(0.005)
        return "ok"

    prompts = ["ok1", "boom", "ok2"]
    bench = SystemPerformanceBenchmark(prompts=prompts, warmup=0)
    result = await bench.run_benchmark(flaky, "flaky-model")

    assert result.num_iterations == 3
    assert result.num_errors == 1


@pytest.mark.asyncio
async def test_percentile_ordering_in_result():
    async def dummy(prompt: str) -> str:
        await asyncio.sleep(0.005)
        return "ok"

    bench = SystemPerformanceBenchmark(
        prompts=[str(i) for i in range(10)], warmup=0
    )
    result = await bench.run_benchmark(dummy, "m")
    assert result.latency_p50_ms <= result.latency_p95_ms
    assert result.latency_p95_ms <= result.latency_p99_ms


@pytest.mark.asyncio
async def test_format_result_contains_key_fields():
    async def dummy(prompt: str) -> str:
        await asyncio.sleep(0.001)
        return "ok"

    bench = SystemPerformanceBenchmark(prompts=["x", "y"], warmup=0)
    result = await bench.run_benchmark(dummy, "fmt-model")
    text = format_result(result)
    assert "fmt-model" in text
    assert "Latency p95" in text
    assert "Throughput" in text
