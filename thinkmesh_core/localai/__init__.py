# LocalAI Module
__version__ = '1.0.0'

from .local_model_manager import LocalModelManager, ModelSize
from .model_optimizer import (
    ModelOptimizer,
    get_optimizer,
    QuantizationLevel,
    OptimizationType
)

try:
    from .runtime_optimizer import (
        RuntimeOptimizer,
        RuntimeParams,
        HardwareProfile,
        ThermalState,
        MODEL_TIERS,
    )
    _RUNTIME_EXPORTS = [
        'RuntimeOptimizer', 'RuntimeParams', 'HardwareProfile',
        'ThermalState', 'MODEL_TIERS',
    ]
except Exception:  # pragma: no cover - defensive import guard
    RuntimeOptimizer = None  # type: ignore
    RuntimeParams = None  # type: ignore
    HardwareProfile = None  # type: ignore
    ThermalState = None  # type: ignore
    MODEL_TIERS = {}  # type: ignore
    _RUNTIME_EXPORTS = []

__all__ = [
    'LocalModelManager',
    'ModelSize',
    'ModelOptimizer',
    'get_optimizer',
    'QuantizationLevel',
    'OptimizationType'
] + _RUNTIME_EXPORTS
