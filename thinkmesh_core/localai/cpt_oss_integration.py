"""
CPT-OSS 20B Integration
=======================

Integration of CPT-OSS 20B (20 billion parameter) language model
with intelligent device capability detection and tiered model selection.

Features:
- Automatic device capability detection
- Quantization support (Q4, Q8, FP16)
- Fallback to smaller models on resource-constrained devices
- Optimized inference for mobile and desktop
"""

import asyncio
import time
import psutil
import platform
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tiers based on device capabilities"""
    LIGHT = "light"          # HRM-27M (512MB)
    STANDARD = "standard"    # Qwen2.5-3B (2-3GB)
    ADVANCED = "advanced"    # CPT-OSS-20B-Q4 (10-12GB)
    PREMIUM = "premium"      # CPT-OSS-20B-Q8 (18-20GB)


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"        # Basic chat, simple Q&A
    MODERATE = "moderate"    # Analysis, reasoning, code review
    ADVANCED = "advanced"    # Complex reasoning, code generation
    EXPERT = "expert"        # Research, strategic planning


@dataclass
class DeviceCapabilities:
    """Device hardware capabilities"""
    total_ram_gb: float
    available_ram_gb: float
    cpu_cores: int
    has_gpu: bool
    storage_available_gb: float
    platform: str
    is_mobile: bool
    battery_level: Optional[int] = None
    is_charging: Optional[bool] = None


@dataclass
class ModelConfig:
    """Configuration for a model"""
    name: str
    tier: ModelTier
    model_path: str
    quantization: str
    memory_required_gb: float
    context_window: int
    max_tokens: int


class CPTOSSIntegration:
    """
    CPT-OSS 20B integration with intelligent model selection
    """
    
    def __init__(self):
        self.is_initialized = False
        self.device_capabilities: Optional[DeviceCapabilities] = None
        self.selected_tier: Optional[ModelTier] = None
        self.loaded_model: Optional[Any] = None
        
        # Model configurations
        self.model_configs: Dict[ModelTier, ModelConfig] = {
            ModelTier.LIGHT: ModelConfig(
                name="hrm-27m",
                tier=ModelTier.LIGHT,
                model_path="models/hrm-27m.bin",
                quantization="INT8",
                memory_required_gb=0.5,
                context_window=4096,
                max_tokens=512
            ),
            ModelTier.STANDARD: ModelConfig(
                name="qwen2.5-3b",
                tier=ModelTier.STANDARD,
                model_path="models/qwen2.5-3b-q8.gguf",
                quantization="Q8",
                memory_required_gb=3.0,
                context_window=32768,
                max_tokens=2048
            ),
            ModelTier.ADVANCED: ModelConfig(
                name="cpt-oss-20b-q4",
                tier=ModelTier.ADVANCED,
                model_path="models/cpt-oss-20b.Q4_K_M.gguf",
                quantization="Q4_K_M",
                memory_required_gb=12.0,
                context_window=8192,
                max_tokens=4096
            ),
            ModelTier.PREMIUM: ModelConfig(
                name="cpt-oss-20b-q8",
                tier=ModelTier.PREMIUM,
                model_path="models/cpt-oss-20b.Q8_0.gguf",
                quantization="Q8_0",
                memory_required_gb=20.0,
                context_window=8192,
                max_tokens=4096
            )
        }
    
    async def initialize(self) -> None:
        """Initialize the CPT-OSS integration"""
        try:
            logger.info("Initializing CPT-OSS 20B integration...")
            
            # Detect device capabilities
            self.device_capabilities = await self._detect_device_capabilities()
            
            # Select optimal model tier
            self.selected_tier = await self._select_optimal_tier()
            
            # Load the selected model
            await self._load_model(self.selected_tier)
            
            self.is_initialized = True
            logger.info(f"CPT-OSS integration initialized with tier: {self.selected_tier.value}")
            
        except Exception as e:
            logger.error(f"Failed to initialize CPT-OSS integration: {e}")
            raise
    
    async def _detect_device_capabilities(self) -> DeviceCapabilities:
        """Detect device hardware capabilities"""
        try:
            # Get system info
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Detect platform
            system = platform.system()
            is_mobile = system in ['Android', 'iOS']
            
            # Check for GPU (simplified check)
            has_gpu = False
            try:
                import torch
                has_gpu = torch.cuda.is_available()
            except ImportError:
                pass
            
            # Get battery info (mobile only)
            battery_level = None
            is_charging = None
            if is_mobile:
                try:
                    battery = psutil.sensors_battery()
                    if battery:
                        battery_level = int(battery.percent)
                        is_charging = battery.power_plugged
                except:
                    pass
            
            capabilities = DeviceCapabilities(
                total_ram_gb=memory.total / (1024**3),
                available_ram_gb=memory.available / (1024**3),
                cpu_cores=psutil.cpu_count(logical=False) or psutil.cpu_count(),
                has_gpu=has_gpu,
                storage_available_gb=disk.free / (1024**3),
                platform=system,
                is_mobile=is_mobile,
                battery_level=battery_level,
                is_charging=is_charging
            )
            
            logger.info(f"Device capabilities detected:")
            logger.info(f"  RAM: {capabilities.available_ram_gb:.1f}GB / {capabilities.total_ram_gb:.1f}GB")
            logger.info(f"  CPU Cores: {capabilities.cpu_cores}")
            logger.info(f"  GPU: {capabilities.has_gpu}")
            logger.info(f"  Storage: {capabilities.storage_available_gb:.1f}GB")
            logger.info(f"  Platform: {capabilities.platform}")
            logger.info(f"  Mobile: {capabilities.is_mobile}")
            
            return capabilities
            
        except Exception as e:
            logger.error(f"Failed to detect device capabilities: {e}")
            # Return minimal capabilities as fallback
            return DeviceCapabilities(
                total_ram_gb=4.0,
                available_ram_gb=2.0,
                cpu_cores=2,
                has_gpu=False,
                storage_available_gb=10.0,
                platform="Unknown",
                is_mobile=True
            )
    
    async def _select_optimal_tier(self) -> ModelTier:
        """Select optimal model tier based on device capabilities"""
        if not self.device_capabilities:
            return ModelTier.LIGHT
        
        caps = self.device_capabilities
        
        # Check for PREMIUM tier (CPT-OSS 20B Q8)
        if (caps.available_ram_gb >= 20 and 
            caps.storage_available_gb >= 25 and
            not caps.is_mobile and
            caps.cpu_cores >= 8):
            logger.info("Device supports PREMIUM tier (CPT-OSS 20B Q8)")
            return ModelTier.PREMIUM
        
        # Check for ADVANCED tier (CPT-OSS 20B Q4)
        if (caps.available_ram_gb >= 12 and 
            caps.storage_available_gb >= 15 and
            caps.cpu_cores >= 6):
            # Additional checks for mobile
            if caps.is_mobile:
                # Only use on high-end tablets when charging
                if caps.battery_level and caps.battery_level > 50 and caps.is_charging:
                    logger.info("Mobile device supports ADVANCED tier (charging, high battery)")
                    return ModelTier.ADVANCED
                else:
                    logger.info("Mobile device: battery constraints, using STANDARD tier")
                    return ModelTier.STANDARD
            else:
                logger.info("Device supports ADVANCED tier (CPT-OSS 20B Q4)")
                return ModelTier.ADVANCED
        
        # Check for STANDARD tier (Qwen 3B)
        if caps.available_ram_gb >= 3 and caps.storage_available_gb >= 5:
            logger.info("Device supports STANDARD tier (Qwen2.5-3B)")
            return ModelTier.STANDARD
        
        # Default to LIGHT tier (HRM 27M)
        logger.info("Device supports LIGHT tier (HRM-27M)")
        return ModelTier.LIGHT
    
    async def _load_model(self, tier: ModelTier) -> None:
        """Load the model for the selected tier"""
        try:
            model_config = self.model_configs[tier]
            model_path = Path(model_config.model_path)
            
            # Check if model file exists
            if not model_path.exists():
                logger.warning(f"Model file not found: {model_path}")
                logger.warning(f"Please download the model from Hugging Face:")
                
                if tier == ModelTier.ADVANCED:
                    logger.warning("  huggingface-cli download TheBloke/CPT-OSS-20B-GGUF cpt-oss-20b.Q4_K_M.gguf")
                elif tier == ModelTier.PREMIUM:
                    logger.warning("  huggingface-cli download TheBloke/CPT-OSS-20B-GGUF cpt-oss-20b.Q8_0.gguf")
                
                # Fallback to lower tier
                if tier == ModelTier.PREMIUM:
                    logger.info("Falling back to ADVANCED tier")
                    await self._load_model(ModelTier.ADVANCED)
                elif tier == ModelTier.ADVANCED:
                    logger.info("Falling back to STANDARD tier")
                    await self._load_model(ModelTier.STANDARD)
                else:
                    logger.warning("Cannot load model, system will use fallback AI")
                return
            
            # Load model using llama-cpp-python
            try:
                from llama_cpp import Llama
                
                # Calculate optimal settings
                n_threads = max(1, self.device_capabilities.cpu_cores - 1)
                n_batch = 512 if self.device_capabilities.available_ram_gb > 8 else 256
                n_gpu_layers = 0  # CPU only for mobile compatibility
                
                logger.info(f"Loading {model_config.name} model...")
                logger.info(f"  Threads: {n_threads}")
                logger.info(f"  Batch size: {n_batch}")
                logger.info(f"  Context window: {model_config.context_window}")
                
                self.loaded_model = Llama(
                    model_path=str(model_path),
                    n_ctx=model_config.context_window,
                    n_batch=n_batch,
                    n_threads=n_threads,
                    n_gpu_layers=n_gpu_layers,
                    use_mmap=True,
                    use_mlock=False,
                    verbose=False
                )
                
                logger.info(f"✅ Model loaded successfully: {model_config.name}")
                
            except ImportError:
                logger.error("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
                raise
            
        except Exception as e:
            logger.error(f"Failed to load model for tier {tier.value}: {e}")
            raise
    
    async def analyze_task_complexity(self, prompt: str) -> TaskComplexity:
        """Analyze task complexity to determine required model tier"""
        prompt_lower = prompt.lower()
        
        # Expert level tasks
        expert_keywords = [
            'research', 'analyze deeply', 'comprehensive analysis', 
            'strategic plan', 'architecture', 'system design',
            'write a paper', 'detailed report'
        ]
        if any(kw in prompt_lower for kw in expert_keywords):
            return TaskComplexity.EXPERT
        
        # Advanced level tasks
        advanced_keywords = [
            'implement', 'create code', 'develop', 'build',
            'complex', 'algorithm', 'optimize', 'refactor',
            'debug', 'solve', 'design'
        ]
        if any(kw in prompt_lower for kw in advanced_keywords):
            return TaskComplexity.ADVANCED
        
        # Moderate level tasks
        moderate_keywords = [
            'explain', 'how does', 'what is', 'compare',
            'analyze', 'evaluate', 'review', 'summarize'
        ]
        if any(kw in prompt_lower for kw in moderate_keywords):
            return TaskComplexity.MODERATE
        
        # Default to simple
        return TaskComplexity.SIMPLE
    
    async def intelligent_routing(self, prompt: str, privacy_mode: str = "balanced") -> Dict[str, Any]:
        """
        Intelligently route request to optimal model based on:
        - Task complexity
        - Device capabilities
        - Privacy settings
        - Battery status (mobile)
        """
        if not self.is_initialized:
            await self.initialize()
        
        # Analyze task complexity
        complexity = await self.analyze_task_complexity(prompt)
        
        # Determine required tier
        required_tier = self._map_complexity_to_tier(complexity)
        
        # Check privacy mode
        if privacy_mode == "strict":
            # Force local processing only
            selected_tier = min(required_tier, self.selected_tier, key=lambda t: t.value)
        else:
            # Use best available tier
            selected_tier = min(required_tier, self.selected_tier, key=lambda t: list(ModelTier).index(t))
        
        # Additional mobile checks
        if self.device_capabilities and self.device_capabilities.is_mobile:
            if self.device_capabilities.battery_level and self.device_capabilities.battery_level < 20:
                # Low battery, use lighter model
                logger.info("Low battery detected, using lighter model")
                selected_tier = ModelTier.LIGHT
            elif not self.device_capabilities.is_charging and selected_tier in [ModelTier.ADVANCED, ModelTier.PREMIUM]:
                # Not charging, avoid heavy models
                logger.info("Not charging, using STANDARD tier to preserve battery")
                selected_tier = ModelTier.STANDARD
        
        return {
            "selected_tier": selected_tier,
            "task_complexity": complexity,
            "model_config": self.model_configs[selected_tier],
            "device_capabilities": self.device_capabilities
        }
    
    def _map_complexity_to_tier(self, complexity: TaskComplexity) -> ModelTier:
        """Map task complexity to required model tier"""
        complexity_tier_map = {
            TaskComplexity.SIMPLE: ModelTier.LIGHT,
            TaskComplexity.MODERATE: ModelTier.STANDARD,
            TaskComplexity.ADVANCED: ModelTier.ADVANCED,
            TaskComplexity.EXPERT: ModelTier.PREMIUM
        }
        return complexity_tier_map.get(complexity, ModelTier.STANDARD)
    
    async def generate(self, prompt: str, max_tokens: int = 512, 
                      temperature: float = 0.7) -> str:
        """Generate text using the loaded model"""
        if not self.loaded_model:
            raise RuntimeError("Model not loaded. Call initialize() first.")
        
        try:
            start_time = time.time()
            
            # Generate response
            response = self.loaded_model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                top_k=40,
                repeat_penalty=1.1,
                stop=["</s>", "Human:", "Assistant:"]
            )
            
            # Extract text
            generated_text = response['choices'][0]['text']
            
            # Calculate metrics
            generation_time = time.time() - start_time
            tokens_generated = response['usage']['completion_tokens']
            tokens_per_second = tokens_generated / generation_time if generation_time > 0 else 0
            
            logger.info(f"Generation complete:")
            logger.info(f"  Tokens: {tokens_generated}")
            logger.info(f"  Time: {generation_time:.2f}s")
            logger.info(f"  Speed: {tokens_per_second:.1f} tokens/s")
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        if not self.selected_tier:
            return {"status": "not_initialized"}
        
        config = self.model_configs[self.selected_tier]
        
        return {
            "tier": self.selected_tier.value,
            "model_name": config.name,
            "quantization": config.quantization,
            "memory_required_gb": config.memory_required_gb,
            "context_window": config.context_window,
            "max_tokens": config.max_tokens,
            "device_capabilities": {
                "ram_gb": self.device_capabilities.total_ram_gb if self.device_capabilities else 0,
                "available_ram_gb": self.device_capabilities.available_ram_gb if self.device_capabilities else 0,
                "cpu_cores": self.device_capabilities.cpu_cores if self.device_capabilities else 0,
                "is_mobile": self.device_capabilities.is_mobile if self.device_capabilities else False
            },
            "is_loaded": self.loaded_model is not None
        }


# Convenience functions
async def initialize_cpt_oss() -> CPTOSSIntegration:
    """Initialize and return CPT-OSS integration"""
    integration = CPTOSSIntegration()
    await integration.initialize()
    return integration


async def auto_generate(prompt: str, privacy_mode: str = "balanced") -> str:
    """Auto-generate with intelligent model selection"""
    integration = await initialize_cpt_oss()
    routing_info = await integration.intelligent_routing(prompt, privacy_mode)
    
    logger.info(f"Routing to tier: {routing_info['selected_tier'].value}")
    logger.info(f"Task complexity: {routing_info['task_complexity'].value}")
    
    response = await integration.generate(prompt)
    return response


if __name__ == "__main__":
    # Test the integration
    async def test():
        print("Testing CPT-OSS 20B Integration...")
        
        integration = CPTOSSIntegration()
        await integration.initialize()
        
        # Get model info
        info = await integration.get_model_info()
        print(f"\nModel Info:")
        print(f"  Tier: {info['tier']}")
        print(f"  Model: {info['model_name']}")
        print(f"  Loaded: {info['is_loaded']}")
        
        # Test prompts
        test_prompts = [
            ("Hello, how are you?", TaskComplexity.SIMPLE),
            ("Explain quantum computing", TaskComplexity.MODERATE),
            ("Write a Python function to implement quicksort", TaskComplexity.ADVANCED),
            ("Design a distributed microservices architecture", TaskComplexity.EXPERT)
        ]
        
        for prompt, expected_complexity in test_prompts:
            print(f"\n{'='*60}")
            print(f"Prompt: {prompt}")
            
            routing = await integration.intelligent_routing(prompt)
            print(f"Complexity: {routing['task_complexity'].value}")
            print(f"Selected Tier: {routing['selected_tier'].value}")
            print(f"Expected: {expected_complexity.value}")
    
    asyncio.run(test())
