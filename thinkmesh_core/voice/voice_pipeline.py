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
    enable_vad: bool = True
    # Opt-in premium cloud tier (inactive unless a key is supplied). Enabling
    # requires privacy_mode=False so cloud use is always an explicit choice.
    enable_cloud_tts: bool = False
    enable_cloud_stt: bool = False
    elevenlabs_api_key: Optional[str] = None
    deepgram_api_key: Optional[str] = None
    # Opt-in LOCAL premium tier via a running OmniVoice Studio instance
    # (OpenAI-compatible HTTP API on localhost). Audio stays on-device, so this
    # is NOT gated on privacy_mode. base_url=None uses the OmniVoice default.
    enable_omnivoice_tts: bool = False
    enable_omnivoice_stt: bool = False
    omnivoice_base_url: Optional[str] = None
    # Local audio cleanup (numpy/scipy, no cloud). On by default, disable-able.
    enable_noise_suppression: bool = True
    enable_output_enhancement: bool = True


class VoicePipeline:
    """Complete voice processing pipeline with STT and TTS."""

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.stt_providers: Dict[str, Dict[str, Any]] = {}
        self.tts_providers: Dict[str, Dict[str, Any]] = {}
        self.initialized = False
        self._voice_io = None
        self._tts_engine = None
        self._vad = None
        self._audio_processor = None
        logger.info("VoicePipeline created")

    def attach_tts_engine(self, tts_engine: Any) -> None:
        """Attach Coqui TTS optimizer from core engines."""
        self._tts_engine = tts_engine
        self.tts_providers["coqui"] = {"type": "local", "active": True, "engine": tts_engine}

    async def initialize(self):
        """Initialize voice providers."""
        await self._init_stt_providers()
        await self._init_tts_providers()
        self._init_vad()
        self._init_audio_processor()
        self.initialized = True
        logger.info("VoicePipeline initialized")

    def _init_audio_processor(self):
        if not (self.config.enable_noise_suppression or self.config.enable_output_enhancement):
            return
        try:
            from core.voice_pipeline.audio_processor import (
                AudioProcessor,
                AudioProcessorConfig,
            )
            self._audio_processor = AudioProcessor(
                AudioProcessorConfig(
                    noise_suppression=self.config.enable_noise_suppression,
                    output_enhancement=self.config.enable_output_enhancement,
                )
            )
            logger.info("Local audio processing enabled")
        except Exception as e:
            logger.warning(f"Audio processor init failed: {e}")

    def _init_vad(self):
        if not self.config.enable_vad:
            return
        try:
            from core.voice_pipeline.vad import VoiceActivityDetector, VADConfig
            self._vad = VoiceActivityDetector(
                VADConfig(prefer_silero=self.config.prefer_local)
            )
            logger.info("Voice activity detection enabled")
        except Exception as e:
            logger.warning(f"VAD init failed: {e}")

    def has_speech(self, audio_data: bytes) -> bool:
        """Return True if the audio buffer contains speech (local VAD)."""
        if self._vad is None:
            return True
        try:
            return self._vad.detect(audio_data).has_speech
        except Exception as e:
            logger.warning(f"VAD detect failed: {e}")
            return True

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

        # Local premium: not gated on privacy_mode (audio stays on-device).
        if self.config.enable_omnivoice_stt:
            try:
                from core.voice_pipeline.cloud_providers import OmniVoiceSTTProvider
                provider = OmniVoiceSTTProvider(
                    {"base_url": self.config.omnivoice_base_url}
                )
                self.stt_providers["omnivoice"] = {
                    "type": "local",
                    "active": provider.available,
                    "engine": provider,
                }
                logger.info(
                    "OmniVoice STT registered (local, %s)", provider.base_url
                )
            except Exception as e:
                logger.warning(f"OmniVoice STT init failed: {e}")

        if not self.config.privacy_mode and self.config.enable_cloud_stt:
            try:
                from core.voice_pipeline.cloud_providers import DeepgramSTTProvider
                provider = DeepgramSTTProvider(
                    {"api_key": self.config.deepgram_api_key}
                )
                self.stt_providers["deepgram"] = {
                    "type": "cloud",
                    "active": provider.available,
                    "engine": provider,
                    "note": "API key required" if not provider.available else "",
                }
                logger.info(
                    "Deepgram STT registered (active=%s)", provider.available
                )
            except Exception as e:
                logger.warning(f"Deepgram STT init failed: {e}")

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

        # Local premium: not gated on privacy_mode (audio stays on-device).
        if self.config.enable_omnivoice_tts:
            try:
                from core.voice_pipeline.cloud_providers import OmniVoiceTTSProvider
                provider = OmniVoiceTTSProvider(
                    {"base_url": self.config.omnivoice_base_url}
                )
                self.tts_providers["omnivoice"] = {
                    "type": "local",
                    "active": provider.available,
                    "engine": provider,
                }
                logger.info(
                    "OmniVoice TTS registered (local, %s)", provider.base_url
                )
            except Exception as e:
                logger.warning(f"OmniVoice TTS init failed: {e}")

        if not self.config.privacy_mode and self.config.enable_cloud_tts:
            try:
                from core.voice_pipeline.cloud_providers import ElevenLabsTTSProvider
                provider = ElevenLabsTTSProvider(
                    {"api_key": self.config.elevenlabs_api_key}
                )
                self.tts_providers["elevenlabs"] = {
                    "type": "cloud",
                    "active": provider.available,
                    "engine": provider,
                    "note": "API key required" if not provider.available else "",
                }
                logger.info(
                    "ElevenLabs TTS registered (active=%s)", provider.available
                )
            except Exception as e:
                logger.warning(f"ElevenLabs TTS init failed: {e}")

    def _local_stt(self, audio_data: bytes) -> str:
        """Local Whisper transcription used directly or as cloud fallback."""
        entry = self.stt_providers.get("whisper")
        engine = entry.get("engine") if entry else None
        if engine and hasattr(engine, "speech_to_text"):
            return engine.speech_to_text(audio_data)
        return "[transcript unavailable]"

    async def transcribe(self, audio_data: bytes, provider: Optional[str] = None) -> str:
        if not self.initialized:
            await self.initialize()

        provider = provider or self.config.stt_provider
        if provider not in self.stt_providers:
            raise ValueError(f"STT provider '{provider}' not available")

        if self._audio_processor is not None:
            audio_data = self._audio_processor.process_input(audio_data)

        engine = self.stt_providers[provider].get("engine")
        # Opt-in cloud provider: transcribe with local Whisper as fallback.
        if engine and hasattr(engine, "transcribe"):
            return await engine.transcribe(audio_data, local_fallback=self._local_stt)
        if engine and hasattr(engine, "speech_to_text"):
            return engine.speech_to_text(audio_data)
        return "[transcript unavailable]"

    def _local_tts(self, text: str) -> bytes:
        """Local Coqui synthesis used directly or as cloud fallback."""
        entry = self.tts_providers.get("coqui")
        engine = entry.get("engine") if entry else None
        if engine and hasattr(engine, "text_to_speech"):
            return engine.text_to_speech(text)
        return b""

    async def synthesize(self, text: str, provider: Optional[str] = None, **kwargs) -> bytes:
        if not self.initialized:
            await self.initialize()

        provider = provider or self.config.tts_provider
        if provider not in self.tts_providers:
            raise ValueError(f"TTS provider '{provider}' not available")

        entry = self.tts_providers[provider]
        engine = entry.get("engine")
        personality = kwargs.get("personality", "professional")
        audio = b""

        if engine and hasattr(engine, "synthesize") and hasattr(engine.synthesize, "__call__"):
            import asyncio, inspect
            if asyncio.iscoroutinefunction(engine.synthesize):
                # Cloud providers accept a local_fallback kwarg; local engines don't.
                if "local_fallback" in inspect.signature(engine.synthesize).parameters:
                    result = await engine.synthesize(text, local_fallback=self._local_tts)
                else:
                    result = await engine.synthesize(text, personality)
                if isinstance(result, bytes):
                    audio = result
                elif result is not None:
                    audio = bytes(result)

        if not audio and engine and hasattr(engine, "text_to_speech"):
            audio = engine.text_to_speech(text)

        if audio and self._audio_processor is not None:
            audio = self._audio_processor.process_output(audio)
        return audio

    def get_status(self) -> Dict:
        return {
            "initialized": self.initialized,
            "stt_providers": list(self.stt_providers.keys()),
            "tts_providers": list(self.tts_providers.keys()),
            "privacy_mode": self.config.privacy_mode,
            "vad_enabled": self._vad is not None,
            "audio_processing_enabled": self._audio_processor is not None,
            "cloud_tts_active": self.tts_providers.get("elevenlabs", {}).get("active", False),
            "cloud_stt_active": self.stt_providers.get("deepgram", {}).get("active", False),
            "omnivoice_tts_active": self.tts_providers.get("omnivoice", {}).get("active", False),
            "omnivoice_stt_active": self.stt_providers.get("omnivoice", {}).get("active", False),
        }
