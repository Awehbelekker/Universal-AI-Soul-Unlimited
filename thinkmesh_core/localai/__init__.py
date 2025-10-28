# LocalAI Module
__version__ = '1.0.0'

from .local_model_manager import LocalModelManager, ModelSize
from .model_optimizer import (
    ModelOptimizer,
    get_optimizer,
    QuantizationLevel,
    OptimizationType
)

__all__ = [
    'LocalModelManager',
    'ModelSize',
    'ModelOptimizer',
    'get_optimizer',
    'QuantizationLevel',
    'OptimizationType'
]
