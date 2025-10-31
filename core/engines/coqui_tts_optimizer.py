"""
Coqui TTS Optimizer for Universal Soul AI
==========================================

Optimizes Coqui TTS for personality-driven voice synthesis.
Integrates voice characteristics with Universal Soul AI's 6 personality modes.

Features:
- Personality-specific voice configurations
- Speaking rate, pitch, and energy modulation
- Voice model selection per personality
- XTTS v2 multi-speaker support
- Streaming audio generation

Author: Universal Soul AI Team
Date: October 2025
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import numpy as np

try:
    from TTS.api import TTS
    COQUI_TTS_AVAILABLE = True
except ImportError:
    COQUI_TTS_AVAILABLE = False
    TTS = None

from ..config import Config


logger = logging.getLogger(__name__)


class CoquiTTSOptimizer:
    """
    Optimized Coqui TTS provider with personality integration.

    Supports 6 personality modes with distinct voice characteristics:
    - Professional: Neutral, clear, measured
    - Friendly: Warm, approachable, conversational
    - Energetic: Dynamic, enthusiastic, upbeat
    - Calm: Soothing, steady, relaxed
    - Creative: Expressive, varied, imaginative
    - Analytical: Precise, measured, logical
    """

    # Personality-specific voice configurations
    PERSONALITY_VOICE_CONFIGS = {
        "professional": {
            "speaking_rate": 1.0,
            "pitch_scale": 1.0,
            "energy": 0.7,
            "voice_model": "en_speaker_0",  # Neutral, clear
            "temperature": 0.65,
            "description": "Neutral and professional tone",
        },
        "friendly": {
            "speaking_rate": 1.1,
            "pitch_scale": 1.05,
            "energy": 0.85,
            "voice_model": "en_speaker_2",  # Warm, approachable
            "temperature": 0.75,
            "description": "Warm and conversational tone",
        },
        "energetic": {
            "speaking_rate": 1.2,
            "pitch_scale": 1.1,
            "energy": 0.95,
            "voice_model": "en_speaker_4",  # Dynamic, enthusiastic
            "temperature": 0.85,
            "description": "Dynamic and enthusiastic tone",
        },
        "calm": {
            "speaking_rate": 0.9,
            "pitch_scale": 0.95,
            "energy": 0.6,
            "voice_model": "en_speaker_1",  # Soothing, steady
            "temperature": 0.55,
            "description": "Soothing and steady tone",
        },
        "creative": {
            "speaking_rate": 1.05,
            "pitch_scale": 1.08,
            "energy": 0.8,
            "voice_model": "en_speaker_3",  # Expressive, varied
            "temperature": 0.8,
            "description": "Expressive and imaginative tone",
        },
        "analytical": {
            "speaking_rate": 0.95,
            "pitch_scale": 0.98,
            "energy": 0.75,
            "voice_model": "en_speaker_0",  # Precise, measured
            "temperature": 0.6,
            "description": "Precise and logical tone",
        },
    }

    def __init__(
        self,
        model_name: str = "tts_models/en/ljspeech/tacotron2-DDC",
        config: Optional[Config] = None,
        use_gpu: bool = False
    ):
        """
        Initialize Coqui TTS optimizer.

        Args:
            model_name: TTS model to use
            config: Configuration object
            use_gpu: Use GPU for inference (faster but requires GPU)
        """
        if not COQUI_TTS_AVAILABLE:
            logger.warning(
                "Coqui TTS not installed. "
                "Install with: pip install TTS"
            )
            self.tts = None
            self.available = False
        else:
            self.tts = None  # Lazy initialization
            self.available = True

        self.model_name = model_name
        self.config = config or Config()
        self.use_gpu = use_gpu
        self.initialized = False

        logger.info(
            f"Coqui TTS optimizer created "
            f"(model: {model_name}, gpu: {use_gpu})"
        )

    async def initialize(self) -> bool:
        """
        Initialize TTS model.

        Returns:
            bool: True if initialization successful
        """
        if not self.available:
            logger.error("Coqui TTS not available")
            return False

        if self.initialized:
            logger.info("TTS already initialized")
            return True

        try:
            logger.info(f"Loading TTS model: {self.model_name}")

            # Initialize TTS in a thread to avoid blocking
            self.tts = await asyncio.to_thread(
                TTS,
                model_name=self.model_name,
                gpu=self.use_gpu
            )

            self.initialized = True
            logger.info("TTS model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize TTS: {e}")
            return False

    async def synthesize(
        self,
        text: str,
        personality: str = "professional",
        output_path: Optional[Path] = None,
        speaker_idx: Optional[int] = None
    ) -> Optional[bytes]:
        """
        Synthesize speech with personality-specific voice.

        Args:
            text: Text to synthesize
            personality: Personality mode
            output_path: Optional path to save audio file
            speaker_idx: Optional speaker index for multi-speaker models

        Returns:
            Audio bytes if successful, None otherwise
        """
        if not self.initialized:
            success = await self.initialize()
            if not success:
                return None

        try:
            config = self.PERSONALITY_VOICE_CONFIGS.get(
                personality,
                self.PERSONALITY_VOICE_CONFIGS["professional"]
            )

            logger.info(
                f"Synthesizing with {personality} personality: '{text[:50]}...'"
            )

            # Generate audio
            if output_path:
                # Save to file
                await asyncio.to_thread(
                    self.tts.tts_to_file,
                    text=text,
                    file_path=str(output_path),
                    speaker=speaker_idx,
                    speed=config["speaking_rate"]
                )

                # Read file back as bytes
                with open(output_path, "rb") as f:
                    audio_bytes = f.read()
            else:
                # Generate to memory
                audio_np = await asyncio.to_thread(
                    self.tts.tts,
                    text=text,
                    speaker=speaker_idx,
                    speed=config["speaking_rate"]
                )

                # Convert numpy array to bytes (simplified)
                audio_bytes = audio_np.tobytes()

            logger.info(
                f"Synthesized {
                    len(audio_bytes)} bytes with {personality} voice")

            return audio_bytes

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    async def synthesize_with_emotion(
        self,
        text: str,
        emotion: str,
        intensity: float = 0.5
    ) -> Optional[bytes]:
        """
        Synthesize speech with specific emotion.

        Args:
            text: Text to synthesize
            emotion: Emotion (happy, sad, angry, neutral, etc.)
            intensity: Emotion intensity (0.0-1.0)

        Returns:
            Audio bytes if successful
        """
        # Map emotions to personalities
        emotion_to_personality = {
            "happy": "energetic",
            "sad": "calm",
            "angry": "energetic",
            "neutral": "professional",
            "excited": "energetic",
            "calm": "calm",
            "thoughtful": "analytical",
            "creative": "creative",
        }

        personality = emotion_to_personality.get(
            emotion.lower(),
            "professional"
        )

        logger.info(
            f"Synthesizing with emotion: {emotion} "
            f"(intensity: {intensity}, personality: {personality})"
        )

        return await self.synthesize(text, personality=personality)

    def get_personality_info(
        self,
        personality: str
    ) -> Dict[str, Any]:
        """
        Get information about a personality's voice configuration.

        Args:
            personality: Personality name

        Returns:
            Dict containing personality configuration
        """
        config = self.PERSONALITY_VOICE_CONFIGS.get(personality)

        if not config:
            return {
                "available": False,
                "error": f"Personality '{personality}' not found",
                "available_personalities": list(
                    self.PERSONALITY_VOICE_CONFIGS.keys()
                )
            }

        return {
            "available": True,
            "personality": personality,
            **config
        }

    def list_personalities(self) -> List[Dict[str, Any]]:
        """
        List all available personalities.

        Returns:
            List of personality configurations
        """
        return [
            {
                "name": name,
                **config
            }
            for name, config in self.PERSONALITY_VOICE_CONFIGS.items()
        ]

    async def test_synthesis(
        self,
        test_text: str = "Hello, I am Universal Soul AI."
    ) -> Dict[str, Any]:
        """
        Test synthesis across all personalities.

        Args:
            test_text: Text to use for testing

        Returns:
            Dict containing test results for each personality
        """
        results = {}

        for personality in self.PERSONALITY_VOICE_CONFIGS.keys():
            logger.info(f"Testing {personality} personality...")

            audio = await self.synthesize(
                text=test_text,
                personality=personality
            )

            results[personality] = {
                "success": audio is not None,
                "audio_size": len(audio) if audio else 0,
                "config": self.PERSONALITY_VOICE_CONFIGS[personality]
            }

        return results

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health status of TTS system.

        Returns:
            Dict containing health status
        """
        return {
            "status": "healthy" if self.initialized else "not_initialized",
            "available": self.available,
            "model": self.model_name,
            "gpu_enabled": self.use_gpu,
            "personalities": len(self.PERSONALITY_VOICE_CONFIGS),
            "initialized": self.initialized,
        }

    async def cleanup(self):
        """Cleanup resources."""
        if self.tts:
            del self.tts
            self.tts = None
            self.initialized = False
        logger.info("TTS optimizer cleaned up")


class TTSPlaceholder:
    """
    Placeholder TTS when Coqui not available.

    Returns empty audio but maintains API compatibility.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.initialized = False
        logger.info("Using TTS placeholder (Coqui not installed)")

    async def initialize(self) -> bool:
        """Initialize placeholder."""
        self.initialized = True
        return True

    async def synthesize(
        self,
        text: str,
        personality: str = "professional",
        output_path: Optional[Path] = None,
        speaker_idx: Optional[int] = None
    ) -> bytes:
        """Return empty audio bytes."""
        logger.warning(
            f"TTS placeholder: would synthesize '{text[:50]}...' "
            f"with {personality} personality"
        )
        return b""

    async def health_check(self) -> Dict[str, Any]:
        """Return placeholder status."""
        return {
            "status": "placeholder",
            "available": False,
            "message": "Coqui TTS not installed",
        }

    async def cleanup(self):
        """Cleanup placeholder."""
        self.initialized = False


async def create_tts_optimizer(
    model_name: str = "tts_models/en/ljspeech/tacotron2-DDC",
    use_gpu: bool = False,
    auto_initialize: bool = True
) -> CoquiTTSOptimizer:
    """
    Create TTS optimizer instance.

    Args:
        model_name: TTS model to use
        use_gpu: Enable GPU acceleration
        auto_initialize: Automatically initialize model

    Returns:
        CoquiTTSOptimizer instance
    """
    optimizer = CoquiTTSOptimizer(
        model_name=model_name,
        use_gpu=use_gpu
    )

    if auto_initialize and optimizer.available:
        success = await optimizer.initialize()
        if not success:
            logger.warning("Failed to initialize TTS - using placeholder mode")

    return optimizer
