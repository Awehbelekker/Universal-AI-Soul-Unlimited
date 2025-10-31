"""
GPU Optimization Configuration for Ollama Models

Provides utilities to optimize GPU memory usage, manage model loading,
and configure inference parameters for better performance.
"""

import json
import logging
import subprocess
import requests
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPUOptimizer:
    """Manage GPU optimization for model inference"""
    
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.api_url = f"{ollama_host}/api"
    
    def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information from system"""
        try:
            # Try NVIDIA GPU first
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,'
                 'memory.free,memory.used', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.strip().split(',')
                return {
                    'type': 'NVIDIA',
                    'name': output[0].strip(),
                    'total_memory_mb': int(
                        output[1].strip().split()[0]
                    ),
                    'free_memory_mb': int(output[2].strip().split()[0]),
                    'used_memory_mb': int(output[3].strip().split()[0])
                }
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            logger.warning(f"Could not get GPU info: {e}")
        
        return {
            'type': 'Unknown',
            'message': 'GPU information not available'
        }
    
    def recommend_quantization(
        self,
        model_size_gb: float,
        available_memory_gb: float
    ) -> str:
        """
        Recommend quantization level based on available memory
        
        Args:
            model_size_gb: Size of full precision model in GB
            available_memory_gb: Available GPU memory in GB
            
        Returns:
            Recommended quantization (q8_0, q4_0, q4_K_M, etc.)
        """
        # Rule of thumb: need ~1.2x model size for inference overhead
        required_q8 = model_size_gb * 1.2
        required_q4 = (model_size_gb / 2) * 1.2
        
        if available_memory_gb >= required_q8:
            return "q8_0"  # Best quality
        elif available_memory_gb >= required_q4:
            return "q4_K_M"  # Good balance
        else:
            return "q4_0"  # Most memory efficient
    
    def get_optimal_model_params(
        self,
        model_name: str,
        task_type: str = "benchmark"
    ) -> Dict[str, Any]:
        """
        Get optimal parameters for model inference
        
        Args:
            model_name: Name of the model
            task_type: Type of task (benchmark, chat, reasoning)
            
        Returns:
            Dictionary of optimal parameters
        """
        base_params = {
            'num_ctx': 2048,  # Context window
            'num_gpu': 99,  # Use all available GPU layers
            'num_thread': 8,  # CPU threads
        }
        
        # Task-specific parameters
        if task_type == "benchmark":
            base_params.update({
                'temperature': 0.1,  # Low randomness for consistency
                'top_p': 0.9,
                'top_k': 40,
                'repeat_penalty': 1.1,
                'num_predict': 100,  # Max tokens to generate
            })
        elif task_type == "reasoning":
            base_params.update({
                'temperature': 0.3,
                'top_p': 0.95,
                'top_k': 50,
                'repeat_penalty': 1.15,
                'num_predict': 512,
            })
        elif task_type == "chat":
            base_params.update({
                'temperature': 0.7,
                'top_p': 0.9,
                'top_k': 40,
                'repeat_penalty': 1.1,
                'num_predict': 256,
            })
        
        return base_params
    
    def configure_ollama_gpu(
        self,
        num_gpu_layers: int = 99,
        context_size: int = 2048
    ) -> bool:
        """
        Configure Ollama GPU settings
        
        Args:
            num_gpu_layers: Number of layers to load on GPU
            context_size: Context window size
            
        Returns:
            True if successful
        """
        try:
            # These would typically be set via environment variables
            # before starting Ollama
            logger.info(f"GPU Configuration:")
            logger.info(f"  - GPU Layers: {num_gpu_layers}")
            logger.info(f"  - Context Size: {context_size}")
            logger.info(
                f"  - Set OLLAMA_NUM_GPU={num_gpu_layers} "
                f"before starting Ollama"
            )
            logger.info(
                f"  - Set OLLAMA_MAX_LOADED_MODELS=1 to save memory"
            )
            
            return True
        except Exception as e:
            logger.error(f"Error configuring GPU: {e}")
            return False
    
    def get_model_memory_estimate(self, model_name: str) -> Dict[str, Any]:
        """Estimate memory requirements for a model"""
        # Rough estimates based on parameter count and quantization
        memory_estimates = {
            'qwen2.5:3b-q8': {'vram_gb': 4, 'ram_gb': 2},
            'qwen2.5:3b-q4': {'vram_gb': 2.5, 'ram_gb': 1.5},
            'qwen2.5:7b-q8': {'vram_gb': 9, 'ram_gb': 4},
            'qwen2.5:7b-q4': {'vram_gb': 5, 'ram_gb': 2.5},
            'qwen2.5:14b-q8': {'vram_gb': 17, 'ram_gb': 8},
            'qwen2.5:14b-q4': {'vram_gb': 9, 'ram_gb': 4.5},
        }
        
        # Find matching estimate
        for key, estimate in memory_estimates.items():
            if key in model_name.lower():
                return estimate
        
        # Default estimate
        return {'vram_gb': 4, 'ram_gb': 2, 'note': 'Estimate only'}
    
    def optimize_for_benchmarking(
        self,
        model_name: str
    ) -> Dict[str, Any]:
        """
        Get optimized configuration for benchmark runs
        
        Args:
            model_name: Name of model to optimize for
            
        Returns:
            Optimized configuration dict
        """
        gpu_info = self.get_gpu_info()
        memory_estimate = self.get_model_memory_estimate(model_name)
        
        config = {
            'model': model_name,
            'gpu_info': gpu_info,
            'memory_estimate': memory_estimate,
            'recommended_params': self.get_optimal_model_params(
                model_name,
                'benchmark'
            ),
        }
        
        # Add warnings if memory might be tight
        if gpu_info.get('type') == 'NVIDIA':
            free_gb = gpu_info.get('free_memory_mb', 0) / 1024
            required_gb = memory_estimate.get('vram_gb', 4)
            
            if free_gb < required_gb:
                config['warning'] = (
                    f"Insufficient GPU memory: {free_gb:.1f}GB free, "
                    f"{required_gb}GB recommended. "
                    f"Model will run on CPU (slower)."
                )
                config['recommendation'] = (
                    f"Consider using smaller quantization or "
                    f"closing other GPU applications"
                )
        
        return config
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all models available in Ollama"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = []
                for model in data.get('models', []):
                    models.append({
                        'name': model['name'],
                        'size_gb': model.get('size', 0) / (1024**3),
                        'modified': model.get('modified_at', ''),
                    })
                return models
        except Exception as e:
            logger.error(f"Error listing models: {e}")
        
        return []
    
    def unload_model(self, model_name: str) -> bool:
        """Unload a model from memory"""
        try:
            # Send empty prompt with keep_alive=0 to unload
            response = requests.post(
                f"{self.api_url}/generate",
                json={
                    'model': model_name,
                    'prompt': '',
                    'keep_alive': 0
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Unloaded model: {model_name}")
                return True
        except Exception as e:
            logger.error(f"Error unloading model: {e}")
        
        return False
    
    def preload_model(
        self,
        model_name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Preload model into memory with specific options"""
        try:
            payload = {
                'model': model_name,
                'prompt': 'Hello',  # Simple prompt to load model
                'stream': False,
                'keep_alive': -1,  # Keep loaded indefinitely
            }
            
            if options:
                payload['options'] = options
            
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                logger.info(f"Preloaded model: {model_name}")
                return True
        except Exception as e:
            logger.error(f"Error preloading model: {e}")
        
        return False


def main():
    """Example usage"""
    optimizer = GPUOptimizer()
    
    # Get GPU info
    print("=== GPU Information ===")
    gpu_info = optimizer.get_gpu_info()
    print(json.dumps(gpu_info, indent=2))
    
    # List available models
    print("\n=== Available Models ===")
    models = optimizer.list_available_models()
    for model in models:
        print(
            f"- {model['name']}: {model['size_gb']:.2f} GB"
        )
    
    # Get optimization config for benchmarking
    print("\n=== Optimization for Qwen2.5-3B ===")
    config = optimizer.optimize_for_benchmarking('qwen2.5:3b')
    print(json.dumps(config, indent=2))
    
    # Memory recommendations
    print("\n=== Quantization Recommendations ===")
    if gpu_info.get('type') == 'NVIDIA':
        free_gb = gpu_info.get('free_memory_mb', 0) / 1024
        
        for model_size in [3, 7, 14]:
            quant = optimizer.recommend_quantization(model_size, free_gb)
            print(f"Qwen2.5-{model_size}B: Use {quant} quantization")


if __name__ == "__main__":
    main()
