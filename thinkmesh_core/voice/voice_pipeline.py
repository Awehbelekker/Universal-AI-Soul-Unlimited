from typing import Any, Dict, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Voice processing configuration"""
    privacy_mode: bool = True
    prefer_local: bool = True
    stt_provider: str = "whisper"
    tts_provider: str = "coqui"


class VoicePipeline:
    """Complete voice processing pipeline with STT and TTS."""

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.stt_providers: Dict[str, Dict[str, Any]] = {}
        self.tts_providers: Dict[str, Dict[str, Any]] = {}
        self.initialized = False
        self._voice_io = None
        self._tts_engine = None
        logger.info("VoicePipeline created")

    def attach_tts_engine(self, tts_engine: Any) -> None:
        """Attach Coqui TTS optimizer from core engines."""
        self._tts_engine = tts_engine
        self.tts_providers["coqui"] = {"type": "local", "active": True, "engine": tts_engine}

    async def initialize(self):
        """Initialize voice providers."""
        await self._init_stt_providers()
        await self._init_tts_providers()
        self.initialized = True
        logger.info("VoicePipeline initialized")

    async def _init_stt_providers(self):
        try:
            from core.voice_pipeline.voice_io import VoiceIO
            self._voice_io = VoiceIO()
            if self._voice_io.stt_available():
                self.stt_providers["whisper"] = {
                    "type": "local",
                    "active": True,
                    "engine": self._voice_io,
                }
                logger.info("Whisper STT available via VoiceIO")
        except Exception as e:
            logger.warning(f"Whisper STT init failed: {e}")

        if not self.config.privacy_mode:
            self.stt_providers.setdefault(
                "deepgram",
                {"type": "cloud", "active": False, "note": "API key required"},
            )

    async def _init_tts_providers(self):
        if self._tts_engine:
            return
        try:
            from core.voice_pipeline.voice_io import VoiceIO
            if self._voice_io is None:
                self._voice_io = VoiceIO()
            if self._voice_io.tts_available():
                self.tts_providers["coqui"] = {
                    "type": "local",
                    "active": True,
                    "engine": self._voice_io,
                }
                logger.info("Coqui TTS available via VoiceIO")
        except Exception as e:
            logger.warning(f"Coqui TTS init failed: {e}")

    async def transcribe(self, audio_data: bytes, provider: Optional[str] = None) -> str:
        if not self.initialized:
            await self.initialize()

        provider = provider or self.config.stt_provider
        if provider not in self.stt_providers:
            raise ValueError(f"STT provider '{provider}' not available")

        engine = self.stt_providers[provider].get("engine")
        if engine and hasattr(engine, "speech_to_text"):
            return engine.speech_to_text(audio_data, language=self.config.stt_provider)
        return "[transcript unavailable]"

    async def synthesize(self, text: str, provider: Optional[str] = None, **kwargs) -> bytes:
        if not self.initialized:
            await self.initialize()

        provider = provider or self.config.tts_provider
        if provider not in self.tts_providers:
            raise ValueError(f"TTS provider '{provider}' not available")

        entry = self.tts_providers[provider]
        engine = entry.get("engine")
        personality = kwargs.get("personality", "professional")

        if engine and hasattr(engine, "synthesize") and hasattr(engine.synthesize, "__call__"):
            import asyncio
            if asyncio.iscoroutinefunction(engine.synthesize):
                result = await engine.synthesize(text, personality)
                if isinstance(result, bytes):
                    return result
                if result is None:
                    return b""
                return bytes(result) if not isinstance(result, bytes) else result

        if engine and hasattr(engine, "text_to_speech"):
            return engine.text_to_speech(text)

        return b""

    def get_status(self) -> Dict:
        return {
            "initialized": self.initialized,
            "stt_providers": list(self.stt_providers.keys()),
            "tts_providers": list(self.tts_providers.keys()),
            "privacy_mode": self.config.privacy_mode,
        }
