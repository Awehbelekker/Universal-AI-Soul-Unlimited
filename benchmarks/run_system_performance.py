#!/usr/bin/env python3
"""
Run System Performance Benchmarks

Measures real runtime performance (latency, throughput, memory, CPU) of the
models available on this device. Complements the accuracy benchmarks
(MMLU/HellaSwag/ARC/TruthfulQA/GSM8K) with a "how fast does it run" view.

Reuses the same model-detection approach as run_baseline_benchmarks.py so the
two runners stay consistent.
"""

import asyncio
import json
import os
import sys
import logging
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from system_performance_benchmark import (  # noqa: E402
    SystemPerformanceBenchmark,
    format_result,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "benchmark_results"


def detect_models() -> list:
    """Detect available models (local files + optional Ollama)."""
    models = []
    for path in ("models/", "models/hrm-checkpoints/", "../models/"):
        if os.path.exists(path):
            for item in os.listdir(path):
                if item.endswith((".gguf", ".bin", ".safetensors")):
                    models.append({
                        "name": item,
                        "type": "local",
                        "path": os.path.join(path, item),
                    })

    # Optional: probe for a running Ollama server and list its models.
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            for m in resp.json().get("models", []):
                models.append({"name": m["name"], "type": "ollama"})
    except Exception:
        logger.info("Ollama not detected (skipping Ollama models)")

    logger.info("Found %d model(s) for performance benchmarking", len(models))
    return models


def make_inference_fn(config: dict):
    """Build an async inference function for a model config."""
    if config["type"] == "ollama":
        import requests

        async def ollama_infer(prompt: str) -> str:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": config["name"],
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 64},
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

        return ollama_infer

    if config["type"] == "local":
        try:
            from llama_cpp import Llama

            llm = Llama(
                model_path=config["path"],
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
            )

            async def local_infer(prompt: str) -> str:
                out = llm(prompt, max_tokens=64, temperature=0.1)
                return out["choices"][0]["text"]

            return local_infer
        except ImportError:
            logger.warning("llama-cpp-python missing; using dummy for %s",
                           config["name"])

    return _dummy_infer


async def _dummy_infer(prompt: str) -> str:
    import random
    await asyncio.sleep(0.02 + random.random() * 0.03)
    return "ok"


def save_results(results: dict) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = (
        f"{OUTPUT_DIR}/system_performance_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", filename)
    return filename


async def main() -> None:
    models = detect_models()
    if not models:
        logger.warning("No models found; using dummy model for demonstration")
        models = [{"name": "dummy-model", "type": "dummy"}]

    bench = SystemPerformanceBenchmark()
    all_results = {}

    for config in models:
        name = config["name"]
        try:
            infer = make_inference_fn(config)
            result = await bench.run_benchmark(infer, name)
            all_results[name] = asdict(result)
            print(format_result(result))
        except Exception as exc:
            logger.error("Error benchmarking %s: %s", name, exc)

    if all_results:
        save_results(all_results)


if __name__ == "__main__":
    asyncio.run(main())
