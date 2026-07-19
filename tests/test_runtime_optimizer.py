"""
Unit tests for the hardware-aware RuntimeOptimizer.

Deterministic: tests inject a HardwareProfile so they never depend on the host's
real RAM/GPU. One smoke test exercises real detection (must not raise).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Add the project root to the Python path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load the module directly by file path. The parent thinkmesh_core package has a
# pre-existing eager import in its __init__.py (unrelated to this module), so we
# bypass it exactly the way the running app loads these submodules.
_spec = importlib.util.spec_from_file_location(
    "runtime_optimizer_under_test",
    project_root / "thinkmesh_core" / "localai" / "runtime_optimizer.py",
)
_mod = importlib.util.module_from_spec(_spec)
# Register before exec so dataclass field resolution can find the module.
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

HardwareProfile = _mod.HardwareProfile
MODEL_TIERS = _mod.MODEL_TIERS
RuntimeOptimizer = _mod.RuntimeOptimizer
ThermalState = _mod.ThermalState


def _cpu_only(ram_gb: float, threads: int) -> HardwareProfile:
    return HardwareProfile(total_ram_gb=ram_gb, cpu_threads=threads)


def _gpu(ram_gb: float, threads: int, vram_free: float) -> HardwareProfile:
    return HardwareProfile(
        total_ram_gb=ram_gb,
        cpu_threads=threads,
        has_cuda=True,
        vram_total_gb=vram_free,
        vram_free_gb=vram_free,
    )


def test_low_memory_cpu_uses_small_context():
    opt = RuntimeOptimizer(_cpu_only(4.0, 4))
    params = opt.recommend_params()
    assert params.num_ctx == 1024
    assert params.num_gpu == 0
    assert params.num_thread == 3  # threads - 1


def test_high_vram_gpu_offloads_all_layers():
    opt = RuntimeOptimizer(_gpu(32.0, 16, vram_free=16.0))
    params = opt.recommend_params()
    assert params.num_gpu == 99
    assert params.num_ctx == 4096


def test_thermal_hot_degrades_to_cpu_small_context():
    opt = RuntimeOptimizer(_gpu(32.0, 16, vram_free=16.0))
    params = opt.recommend_params(ThermalState.HOT)
    assert params.num_gpu == 0
    assert params.num_ctx == 1024
    assert params.num_thread <= 8


def test_thermal_warm_caps_context():
    opt = RuntimeOptimizer(_gpu(32.0, 16, vram_free=16.0))
    params = opt.recommend_params(ThermalState.WARM)
    assert params.num_ctx <= 2048


def test_model_tier_selection_by_ram():
    assert RuntimeOptimizer(_cpu_only(4.0, 4)).select_model_tier() == "light"
    assert RuntimeOptimizer(_cpu_only(8.0, 8)).select_model_tier() == "fast"
    assert RuntimeOptimizer(_cpu_only(16.0, 8)).select_model_tier() == "capable"


def test_profile_respects_tier_context_ceiling():
    # Capable-class GPU but forced to the light tier's context ceiling when RAM
    # is low: light tier caps num_ctx at 1024 regardless of memory.
    opt = RuntimeOptimizer(_gpu(4.0, 8, vram_free=16.0))
    profile = opt.recommend_profile()
    assert profile["tier"] == "light"
    assert profile["options"]["num_ctx"] <= MODEL_TIERS["light"]["max_ctx"]
    assert profile["model"] == MODEL_TIERS["light"]["model"]


def test_options_shape_is_ollama_ready():
    opt = RuntimeOptimizer(_cpu_only(8.0, 8))
    opts = opt.recommend_params().as_options()
    assert set(opts.keys()) == {"num_ctx", "num_gpu", "num_thread"}
    assert all(isinstance(v, int) for v in opts.values())


def test_real_detection_smoke():
    # Must not raise on any host; returns a usable profile.
    hw = RuntimeOptimizer.detect_hardware()
    assert hw.total_ram_gb > 0
    assert hw.cpu_threads >= 1
