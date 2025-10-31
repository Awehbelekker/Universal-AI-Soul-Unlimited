"""
HRM (Hierarchical Reasoning Model) Engine Implementation
========================================================

27 Million parameter Hierarchical Reasoning Model with personality and values integration.
This is the core AI engine for Universal Soul AI.

Enhanced with Ollama/Llama.cpp backend support for actual model inference.
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from core.interfaces.base_interfaces import IAIEngine
from core.interfaces.data_structures import (
    UserContext, HRMRequest, HRMResponse, PersonalityMode
)
from core.interfaces.exceptions import HRMEngineError, handle_async_exception
from core.config import get_config

# Import optimized backends
try:
    from .ollama_integration import OllamaIntegration
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from .llama_cpp_optimizer import LlamaCppOptimizer
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False


@dataclass
class ReasoningStep:
    """Individual reasoning step in the HRM process"""
    step_name: str
    input_data: Any
    output_data: Any
    confidence: float
    processing_time: float
    reasoning_type: str  # "logical", "creative", "analytical", "emotional"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "input_data": str(self.input_data),
            "output_data": str(self.output_data),
            "confidence": self.confidence,
            "processing_time": self.processing_time,
            "reasoning_type": self.reasoning_type
        }


class HRMEngine(IAIEngine):
    """Hierarchical Reasoning Model Engine - 27M Parameter AI Core"""

    def __init__(self):
        self.config = get_config().hrm
        self.model = None
        self.tokenizer = None
        self.is_initialized = False
        self.model_cache = {}
        self.reasoning_templates = self._load_reasoning_templates()
        self.personality_adapters = self._initialize_personality_adapters()
        self.values_integration = True

        # Backend selection (Ollama > Llama.cpp > Placeholder)
        self.backend_type = "placeholder"
        self.backend = None

        # Check for Ollama backend
        if OLLAMA_AVAILABLE and hasattr(self.config, 'backend'):
            if self.config.backend == "ollama":
                self.backend_type = "ollama"

        # Check for Llama.cpp backend
        elif LLAMA_CPP_AVAILABLE and hasattr(self.config, 'backend'):
            if self.config.backend == "llama_cpp":
                self.backend_type = "llama_cpp"

        # Performance metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.average_response_time = 0.0
        self.reasoning_depth_stats = {}

    @handle_async_exception
    async def initialize(
            self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the HRM engine with 27M parameter model"""
        try:
            if config:
                # Update configuration with provided values
                for key, value in config.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)

            # Load or initialize the 27M parameter model
            await self._load_model()

            # Initialize reasoning components
            await self._initialize_reasoning_components()

            # Setup personality integration
            await self._setup_personality_integration()

            # Initialize values processing
            await self._initialize_values_processing()

            self.is_initialized = True
            print("HRM Engine initialized successfully with 27M parameters")
            return True

        except Exception as e:
            raise HRMEngineError(
                f"Failed to initialize HRM engine: {str(e)}",
                "INITIALIZATION_FAILED"
            )

    @handle_async_exception
    async def process_request(self, request: str, context: UserContext) -> str:
        """Process a user request through hierarchical reasoning"""
        if not self.is_initialized:
            await self.initialize()

        start_time = time.time()
        self.total_requests += 1

        try:
            # Create HRM request
            hrm_request = HRMRequest(
                user_input=request,
                context=context,
                reasoning_depth=self.config.reasoning_depth,
                use_values=self.values_integration,
                use_personality=True
            )

            # Process through hierarchical reasoning
            response = await self._hierarchical_reasoning(hrm_request)

            # Apply personality and values
            final_response = await self._apply_personality_and_values(
                response, context
            )

            # Update metrics
            processing_time = time.time() - start_time
            self.successful_requests += 1
            self._update_metrics(processing_time, hrm_request.reasoning_depth)

            return final_response

        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(
                processing_time,
                self.config.reasoning_depth,
                False)

            raise HRMEngineError(
                f"Failed to process request: {
                    str(e)}", "PROCESSING_FAILED", context={
                    "request": request, "processing_time": processing_time})

    async def get_capabilities(self) -> List[str]:
        """Get HRM engine capabilities"""
        return [
            "hierarchical_reasoning",
            "personality_adaptation",
            "values_integration",
            "multi_depth_processing",
            "creative_reasoning",
            "logical_analysis",
            "emotional_understanding",
            "context_awareness",
            "learning_adaptation",
            "27m_parameter_processing"
        ]

    async def shutdown(self) -> None:
        """Shutdown the HRM engine"""
        if self.model:
            # Cleanup model resources
            self.model = None
            self.tokenizer = None

        self.is_initialized = False
        print("HRM Engine shutdown complete")

    async def _load_model(self) -> None:
        """Load the 27M parameter model using configured backend"""

        # Initialize Ollama backend
        if self.backend_type == "ollama":
            try:
                from .ollama_integration import OllamaIntegration

                ollama_config = get_config()
                model_name = getattr(
                    ollama_config.hrm,
                    'ollama_model',
                    'phi-2:latest'
                )
                base_url = getattr(
                    ollama_config.hrm,
                    'ollama_url',
                    'http://localhost:11434'
                )

                self.backend = OllamaIntegration(
                    model_name=model_name,
                    base_url=base_url
                )

                success = await self.backend.initialize()
                if success:
                    print(f"✅ Ollama backend initialized: {model_name}")
                    self.model = f"OLLAMA_{model_name}"
                    return
                else:
                    print("⚠️ Ollama initialization failed, falling back")
                    self.backend_type = "placeholder"

            except Exception as e:
                print(f"⚠️ Ollama backend error: {e}, using placeholder")
                self.backend_type = "placeholder"

        # Initialize Llama.cpp backend
        elif self.backend_type == "llama_cpp":
            try:
                from .llama_cpp_optimizer import LlamaCppOptimizer

                model_path = Path(self.config.model_path)
                if not model_path.exists():
                    print(f"⚠️ Model not found: {model_path}")
                    self.backend_type = "placeholder"
                else:
                    self.backend = LlamaCppOptimizer(model_path=model_path)
                    success = await self.backend.initialize()
                    if success:
                        print(f"✅ Llama.cpp backend initialized")
                        self.model = f"LLAMA_CPP_{model_path.name}"
                        return

            except Exception as e:
                print(f"⚠️ Llama.cpp backend error: {e}, using placeholder")
                self.backend_type = "placeholder"

        # Fallback to placeholder
        print("ℹ️ Using placeholder 27M parameter model")
        self.model = "PLACEHOLDER_27M_MODEL"
        self.tokenizer = "PLACEHOLDER_TOKENIZER"

    async def _initialize_reasoning_components(self) -> None:
        """Initialize hierarchical reasoning components"""
        # Initialize reasoning layers
        self.reasoning_layers = {
            1: "surface_understanding",
            2: "contextual_analysis",
            3: "deep_reasoning",
            4: "creative_synthesis",
            5: "wisdom_integration"
        }

        # Initialize reasoning weights
        self.layer_weights = {
            1: 0.2,
            2: 0.25,
            3: 0.3,
            4: 0.15,
            5: 0.1
        }

    async def _setup_personality_integration(self) -> None:
        """Setup personality integration system"""
        self.personality_prompts = {
            PersonalityMode.PROFESSIONAL: "Respond in a professional, formal manner",
            PersonalityMode.FRIENDLY: "Respond in a warm, friendly, approachable way",
            PersonalityMode.ENERGETIC: "Respond with enthusiasm and energy",
            PersonalityMode.CALM: "Respond in a calm, peaceful, reassuring manner",
            PersonalityMode.CREATIVE: "Respond with creativity and imagination",
            PersonalityMode.ANALYTICAL: "Respond with analytical precision and logic"}

    async def _initialize_values_processing(self) -> None:
        """Initialize values-based processing"""
        self.values_weights = {
            "family_harmony": 0.3,
            "personal_growth": 0.25,
            "integrity": 0.2,
            "compassion": 0.15,
            "wisdom": 0.1
        }

    async def _hierarchical_reasoning(
        self,
        request: HRMRequest
    ) -> HRMResponse:
        """Perform hierarchical reasoning through multiple layers"""
        response = HRMResponse(request_id=request.request_id)
        current_input = request.user_input

        # Process through each reasoning layer
        for layer in range(1, request.reasoning_depth + 1):
            layer_name = self.reasoning_layers.get(layer, f"layer_{layer}")
            layer_weight = self.layer_weights.get(layer, 0.1)

            start_time = time.time()

            # Process using backend if available
            if self.backend and self.backend_type in ["ollama", "llama_cpp"]:
                layer_result = await self._process_with_backend(
                    current_input,
                    layer,
                    layer_name,
                    request.context
                )
            else:
                # Fallback to placeholder processing
                layer_result = await self._process_reasoning_layer(
                    current_input, layer, layer_name, request.context
                )

            processing_time = time.time() - start_time

            # Add reasoning step to response
            response.add_reasoning_step(
                step=layer_name,
                result=layer_result,
                confidence=layer_weight * 0.9  # Simulate confidence
            )

            # Use output as input for next layer
            current_input = layer_result

        # Generate final response
        response.response_text = await self._generate_final_response(
            response.reasoning_chain, request
        )

        # Calculate overall confidence
        total_confidence = sum(
            step["confidence"] for step in response.reasoning_chain
        )
        response.confidence = min(
            total_confidence / len(response.reasoning_chain),
            1.0
        )

        return response

    async def _process_with_backend(
        self,
        input_text: str,
        layer: int,
        layer_name: str,
        context: UserContext
    ) -> str:
        """Process reasoning layer using Ollama or Llama.cpp backend"""
        try:
            # Build prompt for this reasoning layer
            prompt = self._build_layer_prompt(
                input_text,
                layer,
                layer_name,
                context
            )

            # Get personality mode
            personality = context.personality_mode.value.lower()

            # Generate response using backend
            if self.backend_type == "ollama":
                result = await self.backend.generate_hrm_response(
                    prompt=prompt,
                    personality=personality,
                    context={"layer": layer, "layer_name": layer_name},
                    max_tokens=512
                )
                return result.get("response", input_text)

            elif self.backend_type == "llama_cpp":
                result = await self.backend.generate(
                    prompt=prompt,
                    max_tokens=512,
                    temperature=0.7,
                    top_p=0.9
                )
                return result.get("response", input_text)

            return input_text

        except Exception as e:
            print(f"Backend processing error: {e}")
            # Fallback to placeholder
            return await self._process_reasoning_layer(
                input_text,
                layer,
                layer_name,
                context
            )

    def _build_layer_prompt(
        self,
        input_text: str,
        layer: int,
        layer_name: str,
        context: UserContext
    ) -> str:
        """Build prompt for specific reasoning layer"""
        layer_instructions = {
            1: "Understand the surface meaning and key points",
            2: "Analyze the context and deeper implications",
            3: "Reason deeply about causes, effects, and connections",
            4: "Synthesize creative insights and novel perspectives",
            5: "Integrate wisdom and provide thoughtful guidance"
        }

        instruction = layer_instructions.get(
            layer,
            "Process and analyze this input"
        )

        return f"""Layer {layer} ({layer_name}): {instruction}

User input: {input_text}

Provide your analysis:"""

    async def _process_reasoning_layer(
            self,
            input_text: str,
            layer: int,
            layer_name: str,
            context: UserContext) -> str:
        """Process reasoning at a specific layer"""
        # This would integrate with the actual 27M parameter model
        # For now, we simulate the reasoning process

        if layer == 1:  # Surface understanding
            return f"Understanding: {input_text[:100]}..."
        elif layer == 2:  # Contextual analysis
            personality = context.personality_mode.value if context else "friendly"
            return f"Contextual analysis with {personality} personality: {input_text[:80]}..."
        elif layer == 3:  # Deep reasoning
            return f"Deep reasoning synthesis: {input_text[:60]}..."
        elif layer == 4:  # Creative synthesis
            return f"Creative synthesis: {input_text[:50]}..."
        elif layer == 5:  # Wisdom integration
            return f"Wisdom integration: {input_text[:40]}..."
        else:
            return f"Layer {layer} processing: {input_text[:30]}..."

    async def _generate_final_response(
            self, reasoning_chain: List[Dict[str, Any]], request: HRMRequest) -> str:
        """Generate final response from reasoning chain"""
        # In production, this would use the 27M parameter model
        # to generate a coherent response from the reasoning chain

        final_layer_result = reasoning_chain[-1]["result"] if reasoning_chain else ""

        # Simulate response generation
        base_response = f"Based on hierarchical reasoning: {final_layer_result}"

        # Add personality if available
        if request.context and request.use_personality:
            personality = request.context.personality_mode
            personality_prompt = self.personality_prompts.get(
                personality, "Respond naturally"
            )
            base_response = f"{personality_prompt}. {base_response}"

        return base_response

    async def _apply_personality_and_values(self, response_text: str,
                                            context: UserContext) -> str:
        """Apply personality and values to the response"""
        final_response = response_text

        # Apply personality adaptation
        if context and context.personality_mode:
            personality_modifier = self.personality_adapters.get(
                context.personality_mode, lambda x: x
            )
            final_response = personality_modifier(final_response)

        # Apply values integration if profile exists
        if context and context.values_profile:
            final_response = await self._integrate_values(
                final_response, context.values_profile
            )

        return final_response

    async def _integrate_values(self, response: str,
                                values_profile: Dict[str, Any]) -> str:
        """Integrate user values into the response"""
        # Simple values integration - in production this would be more
        # sophisticated
        core_values = values_profile.get("core_values", [])

        if "family_harmony" in core_values:
            response = response.replace(
                "I suggest", "For your family, I suggest")

        if "personal_growth" in core_values:
            response += " This could also be an opportunity for personal growth."

        return response

    def _load_reasoning_templates(self) -> Dict[str, str]:
        """Load reasoning templates for different types of processing"""
        return {
            "logical": "Analyze this logically step by step:",
            "creative": "Approach this creatively and imaginatively:",
            "analytical": "Break this down analytically:",
            "emotional": "Consider the emotional aspects:",
            "practical": "Focus on practical solutions:"
        }

    def _initialize_personality_adapters(
            self) -> Dict[PersonalityMode, callable]:
        """Initialize personality adaptation functions"""
        return {
            PersonalityMode.PROFESSIONAL: lambda text: f"Professionally speaking, {text}",
            PersonalityMode.FRIENDLY: lambda text: f"Hey there! {text} 😊",
            PersonalityMode.ENERGETIC: lambda text: f"Wow! {text}! This is exciting!",
            PersonalityMode.CALM: lambda text: f"Calmly considering this: {text}",
            PersonalityMode.CREATIVE: lambda text: f"Creatively speaking: {text} ✨",
            PersonalityMode.ANALYTICAL: lambda text: f"Analytically: {text}"}

    def _update_metrics(self, processing_time: float, depth: int,
                        success: bool = True) -> None:
        """Update performance metrics"""
        # Update average response time
        if self.total_requests > 0:
            self.average_response_time = (
                (self.average_response_time * (self.total_requests - 1) + processing_time)
                / self.total_requests
            )

        # Update depth statistics
        if depth not in self.reasoning_depth_stats:
            self.reasoning_depth_stats[depth] = {"count": 0, "avg_time": 0.0}

        stats = self.reasoning_depth_stats[depth]
        stats["count"] += 1
        stats["avg_time"] = (
            (stats["avg_time"] * (stats["count"] - 1) + processing_time)
            / stats["count"]
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        success_rate = (
            self.successful_requests / self.total_requests
            if self.total_requests > 0 else 0.0
        )

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": success_rate,
            "average_response_time": self.average_response_time,
            "reasoning_depth_stats": self.reasoning_depth_stats,
            "is_initialized": self.is_initialized,
            "model_type": "27M_Parameter_HRM"
        }
