"""
Llama.cpp Optimizer for Universal Soul AI
=========================================

Optimizes llama-cpp for GGUF model inference with automatic
system resource detection and configuration.

Benefits:
- Automatic thread/batch size optimization based on CPU/RAM
- Memory-mapped model loading for faster startup
- Support for both CPU and GPU inference
- Low-memory optimization for resource-constrained systems

Author: Universal Soul AI Team
Date: October 2025
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import psutil

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None

from ..interfaces.base import BaseLLMProvider
from ..config import Config


logger = logging.getLogger(__name__)


class LlamaCppOptimizer(BaseLLMProvider):
    """
    Optimized llama-cpp provider for GGUF model inference.
    
    Automatically detects system resources and configures
    optimal parameters for inference speed and memory usage.
    """
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        config: Optional[Config] = None,
        n_gpu_layers: int = 0,
        use_mmap: bool = True,
        use_mlock: bool = False
    ):
        """
        Initialize llama-cpp optimizer.
        
        Args:
            model_path: Path to GGUF model file
            config: Configuration object
            n_gpu_layers: Number of layers to offload to GPU (0=CPU only)
            use_mmap: Use memory mapping for model loading
            use_mlock: Lock model in RAM (prevents swapping)
        """
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python not installed. "
                "Install with: pip install llama-cpp-python"
            )
        
        self.config = config or Config()
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.use_mmap = use_mmap
        self.use_mlock = use_mlock
        
        # Calculate optimal settings
        self.optimal_threads = self._calculate_optimal_threads()
        self.optimal_batch_size = self._calculate_batch_size()
        self.optimal_ctx_size = 4096  # Default context window
        
        self.model = None
        self.model_loaded = False
        
        logger.info(
            f"Initialized llama-cpp optimizer: "
            f"threads={self.optimal_threads}, "
            f"batch={self.optimal_batch_size}"
        )
    
    def _calculate_optimal_threads(self) -> int:
        """
        Calculate optimal thread count based on CPU.
        
        Returns:
            Optimal number of threads
        """
        cpu_count = psutil.cpu_count(logical=False)  # Physical cores
        if cpu_count is None:
            cpu_count = 4  # Fallback
        
        # Leave 2 cores for system, use rest for inference
        optimal = max(1, cpu_count - 2)
        logger.info(f"Detected {cpu_count} CPU cores, using {optimal} threads")
        return optimal
    
    def _calculate_batch_size(self) -> int:
        """
        Calculate optimal batch size based on available RAM.
        
        Returns:
            Optimal batch size
        """
        available_ram_gb = psutil.virtual_memory().available / (1024**3)
        
        # Conservative estimate: 27M params ≈ 108MB at FP32
        # Target 25% of available RAM for model + context
        max_batch = min(512, int((available_ram_gb * 0.25) / 0.108))
        optimal = max(8, max_batch)  # Minimum 8
        
        logger.info(
            f"Available RAM: {available_ram_gb:.1f}GB, "
            f"batch size: {optimal}"
        )
        return optimal
    
    def get_optimal_config(self) -> Dict[str, Any]:
        """
        Get optimized llama.cpp configuration.
        
        Returns:
            Dict of optimal configuration parameters
        """
        return {
            "n_threads": self.optimal_threads,
            "n_batch": self.optimal_batch_size,
            "n_ctx": self.optimal_ctx_size,
            "n_gpu_layers": self.n_gpu_layers,
            "use_mmap": self.use_mmap,
            "use_mlock": self.use_mlock,
            "low_vram": True,  # Optimize for systems with limited RAM
            "f16_kv": True,  # Use half-precision for KV cache
            "logits_all": False,  # Only compute logits for last token
            "vocab_only": False,
            "rope_freq_base": 10000.0,
            "rope_freq_scale": 1.0,
            "verbose": False,
        }
    
    async def initialize(self) -> bool:
        """
        Initialize and load the GGUF model.
        
        Returns:
            bool: True if initialization successful
        """
        if self.model_loaded:
            logger.info("Model already loaded")
            return True
        
        if not self.model_path or not Path(self.model_path).exists():
            logger.error(f"Model path not found: {self.model_path}")
            return False
        
        try:
            logger.info(f"Loading GGUF model from: {self.model_path}")
            
            config = self.get_optimal_config()
            self.model = Llama(
                model_path=str(self.model_path),
                **config
            )
            
            # Warm up model with a simple prompt
            logger.info("Warming up model...")
            self.model("Test", max_tokens=1, echo=False)
            
            self.model_loaded = True
            logger.info("Model loaded and warmed up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop_sequences: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using llama-cpp.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            stop_sequences: Optional stop sequences
            **kwargs: Additional generation parameters
            
        Returns:
            Dict containing response and metadata
        """
        if not self.model_loaded:
            success = await self.initialize()
            if not success:
                return {
                    "response": "",
                    "success": False,
                    "error": "Model not loaded"
                }
        
        try:
            result = self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop_sequences or [],
                echo=False,
                **kwargs
            )
            
            return {
                "response": result["choices"][0]["text"],
                "success": True,
                "model": str(self.model_path),
                "tokens_generated": result["usage"]["completion_tokens"],
                "metadata": {
                    "prompt_tokens": result["usage"]["prompt_tokens"],
                    "total_tokens": result["usage"]["total_tokens"],
                }
            }
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {
                "response": "",
                "success": False,
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health status of llama-cpp integration.
        
        Returns:
            Dict containing health status
        """
        return {
            "status": "healthy" if self.model_loaded else "not_loaded",
            "model_loaded": self.model_loaded,
            "model_path": str(self.model_path) if self.model_path else None,
            "threads": self.optimal_threads,
            "batch_size": self.optimal_batch_size,
            "gpu_layers": self.n_gpu_layers,
        }
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.model:
            del self.model
            self.model = None
            self.model_loaded = False
        logger.info("Llama-cpp optimizer cleaned up")


def detect_system_capabilities() -> Dict[str, Any]:
    """
    Detect system capabilities for optimal configuration.
    
    Returns:
        Dict containing system information
    """
    cpu_count_physical = psutil.cpu_count(logical=False) or 4
    cpu_count_logical = psutil.cpu_count(logical=True) or 4
    
    mem = psutil.virtual_memory()
    total_ram_gb = mem.total / (1024**3)
    available_ram_gb = mem.available / (1024**3)
    
    return {
        "cpu": {
            "physical_cores": cpu_count_physical,
            "logical_cores": cpu_count_logical,
            "recommended_threads": max(1, cpu_count_physical - 2),
        },
        "memory": {
            "total_gb": total_ram_gb,
            "available_gb": available_ram_gb,
            "recommended_batch_size": max(
                8,
                min(512, int((available_ram_gb * 0.25) / 0.108))
            ),
        },
        "gpu": {
            "available": False,  # TODO: Add GPU detection
            "recommended_layers": 0,
        }
    }


async def create_optimized_llama_provider(
    model_path: Path,
    auto_initialize: bool = True
) -> LlamaCppOptimizer:
    """
    Create an optimized llama-cpp provider.
    
    Args:
        model_path: Path to GGUF model
        auto_initialize: Whether to auto-initialize
        
    Returns:
        LlamaCppOptimizer instance
    """
    capabilities = detect_system_capabilities()
    
    logger.info(f"System capabilities: {capabilities}")
    
    provider = LlamaCppOptimizer(model_path=model_path)
    
    if auto_initialize:
        success = await provider.initialize()
        if not success:
            logger.warning("Failed to initialize model")
    
    return provider
