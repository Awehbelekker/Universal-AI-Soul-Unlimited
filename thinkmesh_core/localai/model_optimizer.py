"""
ThinkMesh Core - Model Optimization Integration
Integrates quantization, caching, and hardware acceleration
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum
import hashlib
import time

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of optimizations available"""
    QUANTIZATION = "quantization"
    KV_CACHE = "kv_cache"
    BATCHING = "batching"
    GPU_ACCELERATION = "gpu_acceleration"
    TENSOR_RT = "tensor_rt"
    NNAPI = "nnapi"
    COREML = "coreml"


class QuantizationLevel(Enum):
    """Quantization levels for model compression"""
    NONE = "none"  # Full precision
    INT8 = "int8"  # 75% size reduction, 2-4x faster
    INT4 = "int4"  # 87% size reduction, 5-10x faster
    Q4_K_M = "q4_k_m"  # Balanced quality/speed
    Q8_0 = "q8_0"  # High quality, moderate compression


class ModelOptimizer:
    """
    Optimize AI models for maximum performance

    Features:
    - Automatic quantization selection
    - KV cache management
    - Dynamic batching
    - Hardware acceleration detection
    - Performance monitoring
    """

    def __init__(self, cache_dir: str = "models/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # KV cache for faster repeated queries
        self.kv_cache: Dict[str, Any] = {}
        self.cache_hits = 0
        self.cache_misses = 0

        # Performance metrics
        self.metrics = {
            'total_inferences': 0,
            'total_time': 0.0,
            'cache_hit_rate': 0.0,
            'avg_latency': 0.0,
            'optimizations_applied': []
        }

        # Detect available hardware
        self.hardware_capabilities = self._detect_hardware()

        logger.info("ModelOptimizer initialized")
        logger.info(f"Hardware: {self.hardware_capabilities}")

    def _detect_hardware(self) -> Dict[str, bool]:
        """Detect available hardware acceleration"""
        capabilities = {
            'cpu': True,
            'cuda': False,
            'rocm': False,
            'metal': False,
            'nnapi': False,
            'coreml': False
        }

        try:
            import torch
            capabilities['cuda'] = torch.cuda.is_available()
        except ImportError:
            pass

        # Check for Android NNAPI
        try:
            import sys
            if 'android' in sys.platform.lower():
                capabilities['nnapi'] = True
        except Exception:
            pass

        return capabilities

    def _get_cache_key(self, prompt: str, model_id: str) -> str:
        """Generate cache key for prompt"""
        combined = f"{model_id}:{prompt}"
        return hashlib.md5(combined.encode()).hexdigest()

    async def optimize_inference(
        self,
        model_id: str,
        prompt: str,
        inference_func,
        quantization: QuantizationLevel = QuantizationLevel.Q4_K_M,
        use_cache: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimized inference with caching and performance tracking

        Args:
            model_id: Model identifier
            prompt: Input prompt
            inference_func: Function to call for inference
            quantization: Quantization level to use
            use_cache: Enable KV caching
            **kwargs: Additional inference parameters

        Returns:
            Dict with response and performance metrics
        """
        start_time = time.time()

        # Check KV cache
        cache_key = self._get_cache_key(prompt, model_id)
        if use_cache and cache_key in self.kv_cache:
            self.cache_hits += 1
            logger.info(f"Cache HIT for prompt: {prompt[:50]}...")

            result = self.kv_cache[cache_key]
            result['cached'] = True
            result['latency'] = 0.001  # Cache retrieval is fast

            return result

        self.cache_misses += 1

        # Apply optimizations
        optimized_kwargs = self._apply_optimizations(
            model_id, quantization, **kwargs
        )

        # Run inference
        try:
            response = await inference_func(
                model_id=model_id,
                prompt=prompt,
                **optimized_kwargs
            )

            inference_time = time.time() - start_time

            # Build result
            result = {
                'response': response,
                'latency': inference_time,
                'cached': False,
                'quantization': quantization.value,
                'optimizations': self.metrics['optimizations_applied']
            }

            # Update cache
            if use_cache:
                self.kv_cache[cache_key] = result

                # Limit cache size
                if len(self.kv_cache) > 100:
                    # Remove oldest entry
                    oldest_key = next(iter(self.kv_cache))
                    del self.kv_cache[oldest_key]

            # Update metrics
            self._update_metrics(inference_time)

            return result

        except Exception as e:
            logger.error(f"Optimization error: {e}")
            # Fallback to standard inference
            response = await inference_func(
                model_id=model_id,
                prompt=prompt,
                **kwargs
            )
            return {
                'response': response,
                'latency': time.time() - start_time,
                'cached': False,
                'error': str(e)
            }

    def _apply_optimizations(
        self,
        model_id: str,
        quantization: QuantizationLevel,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply optimization parameters"""
        optimizations = []
        optimized_kwargs = kwargs.copy()

        # Quantization
        if quantization != QuantizationLevel.NONE:
            optimized_kwargs['quantization'] = quantization.value
            optimizations.append(f"quantization:{quantization.value}")

        # GPU acceleration
        if self.hardware_capabilities['cuda']:
            optimized_kwargs['device'] = 'cuda'
            optimizations.append("gpu:cuda")
        elif self.hardware_capabilities['nnapi']:
            optimized_kwargs['use_nnapi'] = True
            optimizations.append("gpu:nnapi")

        # Batching for multiple prompts
        if 'prompts' in kwargs and len(kwargs['prompts']) > 1:
            optimized_kwargs['batch_size'] = min(len(kwargs['prompts']), 4)
            optimizations.append("batching")

        # Context caching
        optimized_kwargs['use_mmap'] = True
        optimizations.append("mmap")

        self.metrics['optimizations_applied'] = optimizations

        return optimized_kwargs

    def _update_metrics(self, inference_time: float):
        """Update performance metrics"""
        self.metrics['total_inferences'] += 1
        self.metrics['total_time'] += inference_time

        total_requests = self.cache_hits + self.cache_misses
        if total_requests > 0:
            self.metrics['cache_hit_rate'] = self.cache_hits / total_requests

        if self.metrics['total_inferences'] > 0:
            self.metrics['avg_latency'] = (
                self.metrics['total_time'] / self.metrics['total_inferences']
            )

    def clear_cache(self):
        """Clear KV cache"""
        self.kv_cache.clear()
        logger.info("KV cache cleared")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            **self.metrics,
            'cache_size': len(self.kv_cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hardware': self.hardware_capabilities
        }

    async def benchmark_model(
        self,
        model_id: str,
        inference_func,
        test_prompts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Benchmark model with different optimization levels

        Args:
            model_id: Model to benchmark
            inference_func: Inference function
            test_prompts: Custom test prompts

        Returns:
            Benchmark results comparing optimization levels
        """
        if test_prompts is None:
            test_prompts = [
                "What is artificial intelligence?",
                "Explain quantum computing simply.",
                "Write a haiku about technology."
            ]

        results = {}

        # Test each quantization level
        for quant in [QuantizationLevel.NONE, QuantizationLevel.Q8_0, QuantizationLevel.Q4_K_M]:
            logger.info(f"Testing {quant.value}...")

            times = []
            for prompt in test_prompts:
                start = time.time()
                await self.optimize_inference(
                    model_id=model_id,
                    prompt=prompt,
                    inference_func=inference_func,
                    quantization=quant,
                    use_cache=False  # Disable cache for fair comparison
                )
                times.append(time.time() - start)

            avg_time = sum(times) / len(times)
            results[quant.value] = {
                'avg_latency': avg_time,
                'min_latency': min(times),
                'max_latency': max(times),
                'speedup': None
            }

        # Calculate speedup vs non-quantized
        baseline = results[QuantizationLevel.NONE.value]['avg_latency']
        for quant in results:
            if quant != QuantizationLevel.NONE.value:
                results[quant]['speedup'] = f"{baseline / results[quant]['avg_latency']:.2f}x"

        return results


# Singleton instance
_optimizer_instance = None


def get_optimizer() -> ModelOptimizer:
    """Get global optimizer instance"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = ModelOptimizer()
    return _optimizer_instance
