"""
Ollama Integration for Universal Soul AI
========================================

Privacy-first local LLM inference using Ollama.
Replaces placeholder models with actual phi-2 (2.7B params, quantized).

Benefits:
- Fully local and privacy-first
- Automatic model management (auto-download)
- Better GPU support than llama-cpp
- REST API interface for easy integration
- Supports multiple model backends

Author: Universal Soul AI Team
Date: October 2025
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from datetime import datetime

from ..interfaces.base import BaseLLMProvider
from ..config import Config


logger = logging.getLogger(__name__)


class OllamaIntegration(BaseLLMProvider):
    """
    Ollama integration for local LLM inference.

    Provides privacy-first inference with automatic model management.

    Recommended models (in order of preference):
    - qwen2.5:3b (BEST) - 3B params, 32K context, superior reasoning
    - qwen2.5-coder:3b - Optimized for coding tasks
    - phi-2:latest - 2.7B params, fast but limited 2K context
    - mistral:7b-instruct - 7B params, more capable but slower

    Qwen2.5-3B is recommended because:
    - 32K context window (vs 2K in phi-2) enables complex reasoning
    - Better instruction following for personality adaptation
    - Superior performance on reasoning benchmarks
    - Latest model (Sept 2024) with best-in-class quality
    - Still fast and efficient for local inference
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        base_url: str = "http://localhost:11434",
        model_name: str = "qwen2.5:3b"
    ):
        """
        Initialize Ollama integration.

        Args:
            config: Configuration object
            base_url: Ollama server URL (default: localhost:11434)
            model_name: Model to use for inference
        """
        self.config = config or Config()
        self.base_url = base_url
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=60.0)
        self.model_loaded = False

        logger.info(f"Initialized Ollama integration with model: {model_name}")

    async def initialize(self) -> bool:
        """
        Initialize Ollama connection and ensure model is available.

        Returns:
            bool: True if initialization successful
        """
        try:
            # Check if Ollama is running
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                logger.error("Ollama server not responding")
                return False

            # Check if model is available
            models = response.json().get("models", [])
            model_exists = any(
                m.get("name") == self.model_name for m in models)

            if not model_exists:
                logger.info(f"Model {self.model_name} not found, pulling...")
                await self.load_model(self.model_name)

            self.model_loaded = True
            logger.info(
                f"Ollama initialized successfully with {
                    self.model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {e}")
            return False

    async def load_model(self, model_name: str) -> bool:
        """
        Load/pull a model from Ollama registry.

        Args:
            model_name: Name of model to load (e.g., "phi-2:latest")

        Returns:
            bool: True if model loaded successfully
        """
        try:
            logger.info(f"Pulling model: {model_name}")

            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=300.0
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        # Log progress
                        logger.debug(f"Pull progress: {line}")

            self.model_name = model_name
            self.model_loaded = True
            logger.info(f"Successfully loaded model: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using Ollama model.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            stop_sequences: Optional stop sequences
            **kwargs: Additional generation parameters

        Returns:
            Dict containing response, metadata, and timing
        """
        if not self.model_loaded:
            await self.initialize()

        start_time = datetime.now()

        try:
            request_data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                }
            }

            if stop_sequences:
                request_data["options"]["stop"] = stop_sequences

            # Add any additional kwargs to options
            request_data["options"].update(kwargs)

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=request_data
            )

            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")

            data = response.json()
            elapsed = (datetime.now() - start_time).total_seconds()

            result = {
                "response": data.get(
                    "response",
                    ""),
                "success": True,
                "model": self.model_name,
                "elapsed_time": elapsed,
                "tokens_generated": data.get(
                    "eval_count",
                    0),
                "tokens_per_second": data.get(
                    "eval_count",
                    0) / elapsed if elapsed > 0 else 0,
                "metadata": {
                    "total_duration": data.get(
                        "total_duration",
                        0),
                    "load_duration": data.get(
                        "load_duration",
                        0),
                    "prompt_eval_count": data.get(
                        "prompt_eval_count",
                        0),
                    "eval_count": data.get(
                        "eval_count",
                        0),
                }}

            logger.info(
                f"Generated {result['tokens_generated']} tokens in {elapsed:.2f}s "
                f"({result['tokens_per_second']:.1f} tok/s)"
            )

            return result

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {
                "response": "",
                "success": False,
                "error": str(e),
                "elapsed_time": (datetime.now() - start_time).total_seconds()
            }

    async def generate_hrm_response(
        self,
        prompt: str,
        personality: str = "professional",
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        """
        Generate HRM (Hierarchical Reasoning Model) response.

        Optimized for Universal Soul AI's HRM engine with personality support.

        Args:
            prompt: User prompt
            personality: Personality mode (professional, friendly, energetic, etc.)
            context: Optional context dictionary
            max_tokens: Maximum tokens to generate

        Returns:
            Dict containing response and metadata
        """
        # Adjust generation parameters based on personality
        personality_params = self._get_personality_params(personality)

        # Build system prompt with personality
        system_prompt = self._build_system_prompt(personality, context)
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"

        result = await self.generate(
            prompt=full_prompt,
            max_tokens=max_tokens,
            **personality_params
        )

        if result["success"]:
            result["personality"] = personality
            result["context_used"] = context is not None

        return result

    def _get_personality_params(self, personality: str) -> Dict[str, float]:
        """Get generation parameters based on personality mode."""
        params = {
            "professional": {"temperature": 0.6, "top_p": 0.85},
            "friendly": {"temperature": 0.75, "top_p": 0.9},
            "energetic": {"temperature": 0.85, "top_p": 0.92},
            "calm": {"temperature": 0.5, "top_p": 0.8},
            "creative": {"temperature": 0.9, "top_p": 0.95},
            "analytical": {"temperature": 0.55, "top_p": 0.82},
        }
        return params.get(personality, params["professional"])

    def _build_system_prompt(
        self,
        personality: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build system prompt with personality and context."""
        base_prompt = "You are Universal Soul AI, a helpful AI assistant. "

        personality_prompts = {
            "professional": "You are professional, clear, and concise in your responses.",
            "friendly": "You are warm, approachable, and conversational.",
            "energetic": "You are enthusiastic, dynamic, and engaging.",
            "calm": "You are soothing, patient, and reassuring.",
            "creative": "You are imaginative, expressive, and innovative.",
            "analytical": "You are precise, logical, and detail-oriented.",
        }

        prompt = base_prompt + personality_prompts.get(
            personality,
            personality_prompts["professional"]
        )

        if context:
            prompt += f"\n\nContext: {context.get('summary', '')}"

        return prompt

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health status of Ollama integration.

        Returns:
            Dict containing health status and diagnostics
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_loaded = any(
                    m.get("name") == self.model_name for m in models)

                return {
                    "status": "healthy",
                    "ollama_running": True,
                    "model_loaded": model_loaded,
                    "current_model": self.model_name,
                    "available_models": [m.get("name") for m in models]
                }
            else:
                return {
                    "status": "unhealthy",
                    "ollama_running": False,
                    "error": f"Status code: {response.status_code}"
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "ollama_running": False,
                "error": str(e)
            }

    async def cleanup(self):
        """Cleanup resources."""
        await self.client.aclose()
        logger.info("Ollama integration cleaned up")


# Convenience function for quick usage
async def create_ollama_provider(
    model_name: str = "phi-2:latest",
    auto_initialize: bool = True
) -> OllamaIntegration:
    """
    Create and optionally initialize an Ollama provider.

    Args:
        model_name: Model to use
        auto_initialize: Whether to auto-initialize

    Returns:
        OllamaIntegration instance
    """
    provider = OllamaIntegration(model_name=model_name)

    if auto_initialize:
        success = await provider.initialize()
        if not success:
            logger.warning(
                "Failed to initialize Ollama - may need manual setup")

    return provider
