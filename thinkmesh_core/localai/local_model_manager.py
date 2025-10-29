from typing import Dict, List
# Local Model Manager - Privacy-First AI
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ModelSize(Enum):
    TINY = "tiny"  # <100MB
    SMALL = "small"  # 100MB-1GB
    MEDIUM = "medium"  # 1GB-5GB
    LARGE = "large"  # 5GB-20GB


class LocalModelManager:
    """Manages local AI models for privacy-first inference with optimization"""

    def __init__(self, models_dir: str = "models", enable_optimization: bool = True):
        self.models_dir = models_dir
        self.loaded_models = {}
        self.model_registry = {}
        self.enable_optimization = enable_optimization

        # Initialize optimizer
        if enable_optimization:
            try:
                from .model_optimizer import get_optimizer
                self.optimizer = get_optimizer()
                logger.info("Model optimization enabled")
            except ImportError:
                logger.warning("Optimizer not available, using standard inference")
                self.optimizer = None
        else:
            self.optimizer = None

        logger.info(f"LocalModelManager initialized at {models_dir}")

    def register_model(self, model_id: str, model_path: str,
                      size: ModelSize, capabilities: List[str]):
        """Register a local model"""
        self.model_registry[model_id] = {
            'path': model_path,
            'size': size,
            'capabilities': capabilities,
            'loaded': False
        }
        logger.info(f"Registered model: {model_id} ({size.value})")

    async def load_model(self, model_id: str) -> bool:
        """Load model into memory"""
        if model_id not in self.model_registry:
            raise ValueError(f"Model {model_id} not registered")

        if model_id in self.loaded_models:
            logger.info(f"Model {model_id} already loaded")
            return True

        model_info = self.model_registry[model_id]
        logger.info(f"Loading model: {model_id}")

        # Placeholder for actual model loading
        self.loaded_models[model_id] = {'status': 'loaded'}
        model_info['loaded'] = True

        return True

    async def infer(self, model_id: str, input_data: str,
                   use_optimization: bool = True, **kwargs) -> Dict:
        """
        Run inference on local model with optional optimization

        Args:
            model_id: Model identifier
            input_data: Input prompt/data
            use_optimization: Enable performance optimizations
            **kwargs: Additional inference parameters

        Returns:
            Inference result with performance metrics
        """
        if model_id not in self.loaded_models:
            await self.load_model(model_id)

        logger.info(f"Running inference on {model_id}")

        # Use optimizer if available and enabled
        if use_optimization and self.optimizer:
            async def _infer_func(model_id, prompt, **kw):
                # Actual inference logic here
                return {
                    'model': model_id,
                    'result': f"Optimized inference from {model_id}: {prompt[:50]}...",
                    'privacy': 'local-only'
                }

            result = await self.optimizer.optimize_inference(
                model_id=model_id,
                prompt=input_data,
                inference_func=_infer_func,
                **kwargs
            )

            return {
                **result['response'],
                'latency': result['latency'],
                'cached': result.get('cached', False),
                'optimizations': result.get('optimizations', [])
            }

        # Standard inference without optimization
        return {
            'model': model_id,
            'result': f"Inference result from {model_id}",
            'privacy': 'local-only'
        }

    def unload_model(self, model_id: str):
        """Unload model from memory"""
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]
            self.model_registry[model_id]['loaded'] = False
            logger.info(f"Unloaded model: {model_id}")

    def get_status(self) -> Dict:
        """Get status of all models and optimization metrics"""
        status = {
            'models_dir': self.models_dir,
            'registered': len(self.model_registry),
            'loaded': len(self.loaded_models),
            'optimization_enabled': self.optimizer is not None,
            'models': {
                mid: {
                    'size': info['size'].value,
                    'loaded': info['loaded'],
                    'capabilities': info['capabilities']
                }
                for mid, info in self.model_registry.items()
            }
        }

        # Add optimization metrics if available
        if self.optimizer:
            status['performance'] = self.optimizer.get_metrics()

        return status

    def clear_cache(self):
        """Clear optimization cache"""
        if self.optimizer:
            self.optimizer.clear_cache()
            logger.info("Optimization cache cleared")

    async def benchmark(self, model_id: str) -> Dict:
        """Benchmark model with different optimization levels"""
        if not self.optimizer:
            return {'error': 'Optimizer not available'}

        async def _infer_func(model_id, prompt, **kw):
            return {
                'model': model_id,
                'result': f"Benchmark inference: {prompt}",
                'privacy': 'local-only'
            }

        return await self.optimizer.benchmark_model(
            model_id=model_id,
            inference_func=_infer_func
        )
