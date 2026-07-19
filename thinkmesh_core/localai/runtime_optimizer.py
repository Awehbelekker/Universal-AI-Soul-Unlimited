"""
Runtime Optimizer (hardware-aware inference tuning)
===================================================

The project runs pre-quantized GGUF models via the Ollama HTTP API, so genuine
re-quantization / pruning / distillation of the weights is neither possible nor
honest here (see ADOPTION_PLAN.md 1.2). What *is* real and useful is tuning the
runtime knobs Ollama actually respects and selecting a model tier that fits the
device:

- Hardware-aware runtime parameters (num_ctx / num_gpu / num_thread) scaled to
  measured RAM and VRAM.
- Thermal-aware degradation (reduce context and offload to CPU when hot).
- Device model-tier profiles (light / fast / capable).

Detection uses psutil (RAM/threads) and nvidia-smi (VRAM) when available, and
degrades gracefully to conservative CPU defaults otherwise.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ThermalState(Enum):
    """Coarse thermal state used to scale runtime parameters."""

    NORMAL = "normal"
    WARM = "warm"
    HOT = "hot"


@dataclass
class HardwareProfile:
    """Measured (or conservatively defaulted) device capabilities."""

    total_ram_gb: float
    cpu_threads: int
    has_cuda: bool = False
    vram_total_gb: float = 0.0
    vram_free_gb: float = 0.0


@dataclass
class RuntimeParams:
    """Ollama runtime options this optimizer computes."""

    num_ctx: int = 2048
    num_gpu: int = 0
    num_thread: int = 4

    def as_options(self) -> Dict[str, int]:
        return {
            "num_ctx": self.num_ctx,
            "num_gpu": self.num_gpu,
            "num_thread": self.num_thread,
        }


# Device model-tier profiles: model tag + a sensible context ceiling.
MODEL_TIERS: Dict[str, Dict[str, Any]] = {
    "light": {"model": "qwen2.5:3b", "max_ctx": 1024, "min_ram_gb": 0.0},
    "fast": {"model": "phi", "max_ctx": 2048, "min_ram_gb": 6.0},
    "capable": {"model": "qwen2.5:7b", "max_ctx": 4096, "min_ram_gb": 12.0},
}


class RuntimeOptimizer:
    """Compute hardware- and thermal-aware Ollama runtime parameters."""

    def __init__(self, hardware: Optional[HardwareProfile] = None) -> None:
        self.hardware = hardware or self.detect_hardware()
        logger.info("RuntimeOptimizer hardware: %s", self.hardware)

    @staticmethod
    def detect_hardware() -> HardwareProfile:
        """Measure RAM/threads (psutil) and VRAM (nvidia-smi) when available."""
        total_ram_gb, cpu_threads = 4.0, 4
        try:
            import psutil

            total_ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
            cpu_threads = psutil.cpu_count(logical=True) or 4
        except Exception as e:
            logger.warning("psutil unavailable, using CPU defaults: %s", e)

        has_cuda, vram_total, vram_free = False, 0.0, 0.0
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,memory.free",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                total_mb, free_mb = result.stdout.strip().split("\n")[0].split(",")
                vram_total = round(int(total_mb) / 1024, 1)
                vram_free = round(int(free_mb) / 1024, 1)
                has_cuda = vram_total > 0
        except Exception as e:
            logger.info("No NVIDIA GPU detected (%s); using CPU inference", e)

        return HardwareProfile(
            total_ram_gb=total_ram_gb,
            cpu_threads=cpu_threads,
            has_cuda=has_cuda,
            vram_total_gb=vram_total,
            vram_free_gb=vram_free,
        )

    def recommend_params(
        self, thermal: ThermalState = ThermalState.NORMAL
    ) -> RuntimeParams:
        """Scale num_ctx / num_gpu / num_thread to hardware and thermal state."""
        hw = self.hardware

        # Context window scales with available memory.
        mem_gb = hw.vram_free_gb if hw.has_cuda else hw.total_ram_gb
        if mem_gb >= 12:
            num_ctx = 4096
        elif mem_gb >= 6:
            num_ctx = 2048
        else:
            num_ctx = 1024

        # GPU layers: offload all when CUDA is present, else CPU-only.
        num_gpu = 99 if hw.has_cuda else 0

        # Leave one thread for the OS; never below 1.
        num_thread = max(1, hw.cpu_threads - 1)

        # Thermal-aware degradation: lower power draw when the device is hot.
        if thermal == ThermalState.HOT:
            num_ctx = min(num_ctx, 1024)
            num_gpu = 0
            num_thread = max(1, num_thread // 2)
        elif thermal == ThermalState.WARM:
            num_ctx = min(num_ctx, 2048)
            num_thread = max(1, int(num_thread * 0.75))

        return RuntimeParams(num_ctx=num_ctx, num_gpu=num_gpu, num_thread=num_thread)

    def select_model_tier(self) -> str:
        """Pick the best model tier the device can comfortably run."""
        ram = self.hardware.total_ram_gb
        for tier in ("capable", "fast", "light"):
            if ram >= MODEL_TIERS[tier]["min_ram_gb"]:
                return tier
        return "light"

    def recommend_profile(
        self, thermal: ThermalState = ThermalState.NORMAL
    ) -> Dict[str, Any]:
        """Full recommendation: tier + model + hardware-aware runtime options."""
        tier = self.select_model_tier()
        params = self.recommend_params(thermal)
        # Never exceed the tier's context ceiling.
        params.num_ctx = min(params.num_ctx, MODEL_TIERS[tier]["max_ctx"])
        return {
            "tier": tier,
            "model": MODEL_TIERS[tier]["model"],
            "thermal_state": thermal.value,
            "options": params.as_options(),
            "hardware": {
                "total_ram_gb": self.hardware.total_ram_gb,
                "cpu_threads": self.hardware.cpu_threads,
                "has_cuda": self.hardware.has_cuda,
                "vram_total_gb": self.hardware.vram_total_gb,
            },
        }
