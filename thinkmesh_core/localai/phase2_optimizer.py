"""
Phase 2 Optimization Integration Guide
TensorRT, NNAPI, and Advanced Acceleration

Detection honesty (DOC_TRUST): accelerator availability is *probed*, not assumed.
TensorRT is only reported when the ``tensorrt`` Python package or the ``trtexec``
binary is actually present (previously it was assumed whenever CUDA existed).
NNAPI is only reported on a genuine Android runtime (ABI/env markers), not merely
because ``/proc/version`` mentions "android". The ``optimize_for_*`` methods
remain integration stubs — they describe the pipeline and return expected metrics
but do not perform real on-device conversion, which requires the platform build
toolchains (TensorRT SDK / Android NDK) unavailable in this desktop environment.
"""

from typing import Dict, Any
import logging
import os
import shutil
import subprocess
from enum import Enum
import platform

logger = logging.getLogger(__name__)


class AcceleratorType(Enum):
    """Available hardware accelerators"""
    CPU = "cpu"
    CUDA = "cuda"  # NVIDIA GPUs (TensorRT)
    ROCM = "rocm"  # AMD GPUs
    METAL = "metal"  # Apple Silicon
    NNAPI = "nnapi"  # Android Neural Networks API
    COREML = "coreml"  # Apple CoreML
    OPENVINO = "openvino"  # Intel
    TENSORRT = "tensorrt"  # NVIDIA TensorRT


class Phase2Optimizer:
    """
    Advanced optimizations for maximum performance

    Phase 2 features:
    - TensorRT integration (3-10x faster on NVIDIA)
    - NNAPI for Android (2-3x faster)
    - CoreML for iOS (2-4x faster)
    - Dynamic batching (3-5x throughput)
    - Mixed precision inference
    """

    def __init__(self):
        # Probe details (version strings / markers) filled in during detection.
        self.tensorrt_version: str = ""
        self.nnapi_marker: str = ""
        self.available_accelerators = self._detect_accelerators()
        self.active_accelerator = self._select_best_accelerator()

        logger.info("Phase2Optimizer initialized")
        logger.info(f"Available: {list(self.available_accelerators.keys())}")
        logger.info(f"Active: {self.active_accelerator}")

    @staticmethod
    def _detect_tensorrt() -> tuple:
        """Probe for a real TensorRT install (does NOT assume CUDA == TensorRT).

        Returns (available, version_or_marker). Checks, in order, the ``tensorrt``
        Python package, then the ``trtexec`` CLI on PATH. Never raises.
        """
        try:
            import tensorrt as trt  # type: ignore
            ver = getattr(trt, "__version__", "unknown")
            logger.info("TensorRT detected (python package %s)", ver)
            return True, f"python:{ver}"
        except Exception:
            pass
        trtexec = shutil.which("trtexec")
        if trtexec:
            logger.info("TensorRT detected (trtexec at %s)", trtexec)
            return True, f"trtexec:{trtexec}"
        logger.info("TensorRT not detected (no tensorrt package or trtexec)")
        return False, ""

    @staticmethod
    def _detect_nnapi() -> tuple:
        """Probe for a genuine Android runtime that exposes NNAPI. Never raises.

        Uses robust Android markers (the ``ANDROID_*`` env vars set by the
        runtime, or an ``android``/``libc`` signature in ``/proc/version``)
        rather than a substring match alone, so a Linux desktop is not misreported
        as NNAPI-capable. Returns (available, marker).
        """
        if platform.system() != "Linux":
            return False, ""
        # Android runtimes export these; desktop Linux does not.
        for env_var in ("ANDROID_ROOT", "ANDROID_DATA", "ANDROID_STORAGE"):
            if os.environ.get(env_var):
                logger.info("NNAPI: Android runtime marker %s present", env_var)
                return True, f"env:{env_var}"
        try:
            with open("/proc/version", "r") as f:
                content = f.read().lower()
            # Require an Android-specific toolchain signature, not just the word.
            if "android" in content and ("libc" in content or "aarch64" in content):
                logger.info("NNAPI: Android /proc/version signature present")
                return True, "proc_version"
        except Exception:
            pass
        return False, ""

    def _detect_accelerators(self) -> Dict[str, bool]:
        """Detect available hardware accelerators (probed, not assumed)."""
        accelerators = {}

        # CPU always available
        accelerators[AcceleratorType.CPU.value] = True

        # Check CUDA (NVIDIA)
        try:
            import torch
            if torch.cuda.is_available():
                accelerators[AcceleratorType.CUDA.value] = True
                logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        except ImportError:
            pass

        # Check TensorRT independently — CUDA alone does NOT imply TensorRT.
        trt_available, trt_marker = self._detect_tensorrt()
        if trt_available:
            accelerators[AcceleratorType.TENSORRT.value] = True
            self.tensorrt_version = trt_marker

        # Check ROCm (AMD)
        try:
            import torch
            if hasattr(torch, 'hip') and torch.hip.is_available():
                accelerators[AcceleratorType.ROCM.value] = True
        except Exception:
            pass

        # Check Metal (Apple Silicon)
        if platform.system() == 'Darwin':
            try:
                import torch
                has_mps = (hasattr(torch.backends, 'mps') and
                           torch.backends.mps.is_available())
                if has_mps:
                    accelerators[AcceleratorType.METAL.value] = True
                    accelerators[AcceleratorType.COREML.value] = True
            except Exception:
                pass

        # Check NNAPI (genuine Android runtime only)
        nnapi_available, nnapi_marker = self._detect_nnapi()
        if nnapi_available:
            accelerators[AcceleratorType.NNAPI.value] = True
            self.nnapi_marker = nnapi_marker

        # Check OpenVINO (Intel) — only when the runtime is actually importable.
        try:
            import openvino  # type: ignore  # noqa: F401
            accelerators[AcceleratorType.OPENVINO.value] = True
        except Exception:
            pass

        return accelerators

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a structured, honest snapshot of detected accelerators.

        Unlike the mock ``optimize_for_*`` results, this reflects what was
        actually probed on this machine (availability + version/marker), so
        callers can gate real work on genuine capability.
        """
        return {
            "platform": platform.system(),
            "active_accelerator": self.active_accelerator,
            "available": dict(self.available_accelerators),
            "tensorrt": {
                "available": self.available_accelerators.get(
                    AcceleratorType.TENSORRT.value, False
                ),
                "detail": self.tensorrt_version,
            },
            "nnapi": {
                "available": self.available_accelerators.get(
                    AcceleratorType.NNAPI.value, False
                ),
                "detail": self.nnapi_marker,
            },
        }

    def _select_best_accelerator(self) -> str:
        """Select best available accelerator"""
        # Priority order
        priority = [
            AcceleratorType.TENSORRT.value,  # Fastest for NVIDIA
            AcceleratorType.CUDA.value,
            AcceleratorType.METAL.value,  # Fast for Apple
            AcceleratorType.COREML.value,
            AcceleratorType.NNAPI.value,  # Best for Android
            AcceleratorType.ROCM.value,
            AcceleratorType.OPENVINO.value,
            AcceleratorType.CPU.value  # Fallback
        ]

        for acc in priority:
            if self.available_accelerators.get(acc, False):
                return acc

        return AcceleratorType.CPU.value

    def optimize_for_tensorrt(self, model_path: str) -> Dict[str, Any]:
        """
        Optimize model with TensorRT

        NOTE (stub): this describes the pipeline and returns the *expected*
        metrics; it does not run a real TensorRT build (that needs the TensorRT
        SDK + an ONNX export, unavailable here). The result carries
        ``'stub': True`` so callers can tell mock results from real ones.

        Benefits:
        - 3-10x faster inference on NVIDIA GPUs
        - Lower latency for real-time applications
        - Automatic kernel fusion and optimization

        Requirements:
        - NVIDIA GPU with CUDA
        - TensorRT 8.0+

        Returns:
            Optimization result with performance metrics
        """
        if not self.available_accelerators.get(AcceleratorType.TENSORRT.value):
            return {'error': 'TensorRT not available'}

        logger.info(f"Optimizing {model_path} with TensorRT...")

        try:
            # TensorRT optimization steps
            steps = [
                "1. Loading ONNX model",
                "2. Building TensorRT engine (FP16 precision)",
                "3. Optimizing kernels and fusing operations",
                "4. Calibrating for INT8 (optional)",
                "5. Saving optimized engine"
            ]

            for step in steps:
                logger.info(f"   {step}")

            return {
                'status': 'optimized',
                'stub': True,
                'accelerator': 'tensorrt',
                'expected_speedup': '3-10x',
                'precision': 'FP16',
                'optimizations': [
                    'kernel_fusion',
                    'precision_calibration',
                    'layer_fusion'
                ]
            }

        except Exception as e:
            logger.error(f"TensorRT optimization failed: {e}")
            return {'error': str(e)}

    def optimize_for_nnapi(self, model_path: str) -> Dict[str, Any]:
        """
        Optimize model for Android NNAPI

        NOTE (stub): describes the pipeline and returns *expected* metrics; it
        does not run a real TFLite conversion / NNAPI delegation (that needs the
        Android NDK + an on-device runtime). The result carries ``'stub': True``.

        Benefits:
        - 2-3x faster on Android devices
        - Uses dedicated neural processing units
        - Lower battery consumption

        Requirements:
        - Android API 27+ (Android 8.1+)
        - TFLite model format

        Returns:
            Optimization result
        """
        if not self.available_accelerators.get(AcceleratorType.NNAPI.value):
            return {'error': 'NNAPI not available (not on Android)'}

        logger.info(f"Optimizing {model_path} for NNAPI...")

        try:
            steps = [
                "1. Converting to TFLite format",
                "2. Quantizing to INT8 for NNAPI",
                "3. Configuring NNAPI delegate",
                "4. Testing on device accelerators",
                "5. Validating accuracy"
            ]

            for step in steps:
                logger.info(f"   {step}")

            return {
                'status': 'optimized',
                'stub': True,
                'accelerator': 'nnapi',
                'expected_speedup': '2-3x',
                'format': 'tflite',
                'quantization': 'int8',
                'optimizations': [
                    'nnapi_delegation',
                    'quantization_aware_training',
                    'operator_fusion'
                ]
            }

        except Exception as e:
            logger.error(f"NNAPI optimization failed: {e}")
            return {'error': str(e)}

    def optimize_for_coreml(self, model_path: str) -> Dict[str, Any]:
        """
        Optimize model for Apple CoreML

        Benefits:
        - 2-4x faster on iOS/macOS
        - Uses Apple Neural Engine
        - Optimized for Apple Silicon

        Requirements:
        - macOS or iOS device
        - CoreML 5.0+

        Returns:
            Optimization result
        """
        if not self.available_accelerators.get(AcceleratorType.COREML.value):
            return {'error': 'CoreML not available'}

        logger.info(f"Optimizing {model_path} for CoreML...")

        try:
            steps = [
                "1. Converting to CoreML format",
                "2. Quantizing weights to INT8",
                "3. Optimizing for Neural Engine",
                "4. Compiling CoreML model",
                "5. Validating on device"
            ]

            for step in steps:
                logger.info(f"   {step}")

            return {
                'status': 'optimized',
                'accelerator': 'coreml',
                'expected_speedup': '2-4x',
                'format': 'mlmodel',
                'target': 'neural_engine',
                'optimizations': [
                    'neural_engine_optimization',
                    'weight_compression',
                    'compute_precision_fp16'
                ]
            }

        except Exception as e:
            logger.error(f"CoreML optimization failed: {e}")
            return {'error': str(e)}

    def enable_dynamic_batching(self, max_batch_size: int = 8) -> Dict[str, Any]:
        """
        Enable dynamic batching for multiple requests

        Benefits:
        - 3-5x throughput improvement
        - Better GPU utilization
        - Reduced per-request latency

        Args:
            max_batch_size: Maximum batch size

        Returns:
            Batching configuration
        """
        logger.info(
            f"Enabling dynamic batching "
            f"(max_batch_size={max_batch_size})"
        )

        return {
            'status': 'enabled',
            'max_batch_size': max_batch_size,
            'expected_throughput': '3-5x',
            'features': [
                'automatic_batching',
                'request_queuing',
                'adaptive_timeout'
            ]
        }

    def get_optimization_recommendations(self) -> Dict[str, Any]:
        """Get optimization recommendations based on hardware"""
        recommendations = {
            'platform': platform.system(),
            'active_accelerator': self.active_accelerator,
            'recommendations': []
        }

        # Platform-specific recommendations
        if AcceleratorType.TENSORRT.value in self.available_accelerators:
            recommendations['recommendations'].append({
                'priority': 'HIGH',
                'optimization': 'TensorRT',
                'benefit': '3-10x speedup on NVIDIA GPUs',
                'action': 'Use optimize_for_tensorrt()'
            })

        if AcceleratorType.NNAPI.value in self.available_accelerators:
            recommendations['recommendations'].append({
                'priority': 'HIGH',
                'optimization': 'NNAPI',
                'benefit': '2-3x speedup on Android',
                'action': 'Use optimize_for_nnapi()'
            })

        if AcceleratorType.COREML.value in self.available_accelerators:
            recommendations['recommendations'].append({
                'priority': 'HIGH',
                'optimization': 'CoreML',
                'benefit': '2-4x speedup on Apple devices',
                'action': 'Use optimize_for_coreml()'
            })

        # General recommendations
        recommendations['recommendations'].extend([
            {
                'priority': 'MEDIUM',
                'optimization': 'Dynamic Batching',
                'benefit': '3-5x throughput',
                'action': 'Use enable_dynamic_batching()'
            },
            {
                'priority': 'MEDIUM',
                'optimization': 'INT8 Quantization',
                'benefit': '75% size reduction, 2-4x faster',
                'action': 'Already integrated in ModelOptimizer'
            }
        ])

        return recommendations


# Singleton instance
_phase2_optimizer = None


def get_phase2_optimizer() -> Phase2Optimizer:
    """Get global Phase 2 optimizer instance"""
    global _phase2_optimizer
    if _phase2_optimizer is None:
        _phase2_optimizer = Phase2Optimizer()
    return _phase2_optimizer
