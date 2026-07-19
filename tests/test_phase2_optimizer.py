"""
Unit tests for Phase2Optimizer capability detection.

Focus on *honest* detection: TensorRT must not be reported merely because CUDA
exists (it requires a real tensorrt package / trtexec), and NNAPI must be False
off a genuine Android runtime. Detection must never raise on any host.

Loaded by file path — the module uses only stdlib imports, so this bypasses the
pre-existing eager-import error in the top-level thinkmesh_core/__init__.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

_spec = importlib.util.spec_from_file_location(
    "phase2_optimizer_under_test",
    project_root / "thinkmesh_core" / "localai" / "phase2_optimizer.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

Phase2Optimizer = _mod.Phase2Optimizer
AcceleratorType = _mod.AcceleratorType
get_phase2_optimizer = _mod.get_phase2_optimizer


def _patch_probes(monkeypatch, *, trt=(False, ""), nnapi=(False, "")):
    """Force deterministic probe results regardless of host hardware."""
    monkeypatch.setattr(Phase2Optimizer, "_detect_tensorrt", staticmethod(lambda: trt))
    monkeypatch.setattr(Phase2Optimizer, "_detect_nnapi", staticmethod(lambda: nnapi))


def test_detection_smoke_never_raises():
    # Real detection on the actual host must not raise and must include CPU.
    opt = Phase2Optimizer()
    assert opt.available_accelerators.get(AcceleratorType.CPU.value) is True
    assert isinstance(opt.active_accelerator, str)


def test_tensorrt_not_assumed_from_cuda(monkeypatch):
    # Probe says "no TensorRT" => it must be absent even if CUDA is present.
    _patch_probes(monkeypatch, trt=(False, ""))
    opt = Phase2Optimizer()
    assert AcceleratorType.TENSORRT.value not in opt.available_accelerators
    caps = opt.get_capabilities()
    assert caps["tensorrt"]["available"] is False


def test_tensorrt_reported_when_probe_succeeds(monkeypatch):
    _patch_probes(monkeypatch, trt=(True, "python:10.0.1"))
    opt = Phase2Optimizer()
    assert opt.available_accelerators.get(AcceleratorType.TENSORRT.value) is True
    caps = opt.get_capabilities()
    assert caps["tensorrt"]["available"] is True
    assert caps["tensorrt"]["detail"] == "python:10.0.1"
    # TensorRT wins the priority order for active accelerator.
    assert opt.active_accelerator == AcceleratorType.TENSORRT.value


def test_nnapi_false_off_android(monkeypatch):
    _patch_probes(monkeypatch, nnapi=(False, ""))
    opt = Phase2Optimizer()
    assert AcceleratorType.NNAPI.value not in opt.available_accelerators
    assert opt.get_capabilities()["nnapi"]["available"] is False


def test_nnapi_reported_when_probe_succeeds(monkeypatch):
    _patch_probes(monkeypatch, nnapi=(True, "env:ANDROID_ROOT"))
    opt = Phase2Optimizer()
    assert opt.available_accelerators.get(AcceleratorType.NNAPI.value) is True
    assert opt.get_capabilities()["nnapi"]["detail"] == "env:ANDROID_ROOT"


def test_get_capabilities_shape(monkeypatch):
    _patch_probes(monkeypatch)
    caps = Phase2Optimizer().get_capabilities()
    for key in ("platform", "active_accelerator", "available", "tensorrt", "nnapi"):
        assert key in caps
    assert isinstance(caps["available"], dict)
    assert set(caps["tensorrt"]) == {"available", "detail"}
    assert set(caps["nnapi"]) == {"available", "detail"}


def test_optimize_tensorrt_errors_when_unavailable(monkeypatch):
    _patch_probes(monkeypatch, trt=(False, ""))
    result = Phase2Optimizer().optimize_for_tensorrt("model.onnx")
    assert result == {"error": "TensorRT not available"}


def test_optimize_tensorrt_stub_when_available(monkeypatch):
    _patch_probes(monkeypatch, trt=(True, "python:10.0.1"))
    result = Phase2Optimizer().optimize_for_tensorrt("model.onnx")
    # Clearly labeled as a stub, not a real build.
    assert result["status"] == "optimized"
    assert result["stub"] is True
    assert result["accelerator"] == "tensorrt"


def test_optimize_nnapi_errors_when_unavailable(monkeypatch):
    _patch_probes(monkeypatch, nnapi=(False, ""))
    result = Phase2Optimizer().optimize_for_nnapi("model")
    assert result == {"error": "NNAPI not available (not on Android)"}


def test_optimize_nnapi_stub_when_available(monkeypatch):
    _patch_probes(monkeypatch, nnapi=(True, "env:ANDROID_ROOT"))
    result = Phase2Optimizer().optimize_for_nnapi("model")
    assert result["status"] == "optimized"
    assert result["stub"] is True
    assert result["accelerator"] == "nnapi"


def test_recommendations_include_active_and_general(monkeypatch):
    _patch_probes(monkeypatch)
    recs = Phase2Optimizer().get_optimization_recommendations()
    assert "active_accelerator" in recs
    # General recommendations are always appended.
    labels = [r["optimization"] for r in recs["recommendations"]]
    assert "Dynamic Batching" in labels
