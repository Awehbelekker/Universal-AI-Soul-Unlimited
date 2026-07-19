"""
Premium Voice Providers (opt-in)
================================

Optional premium voice tiers. The local stack (Whisper/Coqui/Edge) remains the
default per VISION.md; everything here is strictly OPT-IN and degrades to the
caller-provided local fallback on any error.

Two tiers are provided:

- **Local premium (recommended):** ``OmniVoiceTTSProvider`` /
  ``OmniVoiceSTTProvider`` talk to a locally running OmniVoice Studio via its
  OpenAI-compatible HTTP API (default ``http://localhost:3900/v1``). No data
  leaves the machine and no API key is required. OmniVoice Studio is AGPL-3.0;
  we integrate over HTTP to a **separate process** and vendor none of its code,
  so this is mere aggregation and does NOT impose AGPL on this project.
- **Cloud premium:** ``ElevenLabsTTSProvider`` (TTS) / ``DeepgramSTTProvider``
  (STT). Inactive unless an API key is supplied (via config or the documented
  environment variable). These send audio/text to third-party servers, so they
  are additionally gated on ``privacy_mode=False`` by the pipeline.

Requires aiohttp (already declared in requirements.txt) only when actually used.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Environment variables checked when no explicit key is configured.
ELEVENLABS_ENV_KEY = "ELEVENLABS_API_KEY"
DEEPGRAM_ENV_KEY = "DEEPGRAM_API_KEY"

# Local OmniVoice Studio OpenAI-compatible API (separate process; no key).
OMNIVOICE_ENV_URL = "OMNIVOICE_BASE_URL"
OMNIVOICE_DEFAULT_URL = "http://localhost:3900/v1"


def _probe_aiohttp() -> bool:
    try:
        __import__("aiohttp")
        return True
    except Exception:
        return False


class ElevenLabsTTSProvider:
    """Opt-in ElevenLabs text-to-speech. Inactive without an API key."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.api_key = config.get("api_key") or os.getenv(ELEVENLABS_ENV_KEY)
        self.voice_id = config.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        self.model_id = config.get("model_id", "eleven_monolingual_v1")
        self.base_url = "https://api.elevenlabs.io/v1"
        self.voice_settings = {
            "stability": config.get("stability", 0.75),
            "similarity_boost": config.get("similarity_boost", 0.75),
            "style": config.get("style", 0.0),
            "use_speaker_boost": config.get("use_speaker_boost", True),
        }
        self._session = None

    @property
    def available(self) -> bool:
        return bool(self.api_key) and _probe_aiohttp()

    async def _ensure_session(self):
        import aiohttp

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
            )
        return self._session

    async def synthesize(
        self,
        text: str,
        local_fallback: Optional[Callable[[str], Awaitable[bytes]]] = None,
        voice_config: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Return audio bytes from ElevenLabs, else the local fallback."""
        if not self.available:
            logger.info("ElevenLabs unavailable (no key/aiohttp); using local TTS")
            return await self._fallback(text, local_fallback)
        try:
            session = await self._ensure_session()
            settings = {**self.voice_settings, **(voice_config or {})}
            payload = {"text": text, "model_id": self.model_id, "voice_settings": settings}
            url = f"{self.base_url}/text-to-speech/{self.voice_id}"
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.error(f"ElevenLabs error {resp.status}: {await resp.text()}")
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
        return await self._fallback(text, local_fallback)

    async def _fallback(self, text: str, fn) -> bytes:
        if fn is not None:
            result = fn(text)
            if hasattr(result, "__await__"):
                result = await result
            return result or b""
        return b""

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None


class DeepgramSTTProvider:
    """Opt-in Deepgram speech-to-text. Inactive without an API key."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.api_key = config.get("api_key") or os.getenv(DEEPGRAM_ENV_KEY)
        self.base_url = "https://api.deepgram.com/v1"
        self.stt_settings = {
            "model": config.get("model", "nova-2"),
            "language": config.get("language", "en-US"),
            "punctuate": config.get("punctuate", True),
            "smart_format": config.get("smart_format", True),
        }
        self._session = None

    @property
    def available(self) -> bool:
        return bool(self.api_key) and _probe_aiohttp()

    async def _ensure_session(self):
        import aiohttp

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"Authorization": f"Token {self.api_key}", "Content-Type": "audio/wav"},
            )
        return self._session

    async def transcribe(
        self,
        audio_data: bytes,
        local_fallback: Optional[Callable[[bytes], Awaitable[str]]] = None,
    ) -> str:
        """Return a transcript from Deepgram, else the local fallback."""
        if not self.available:
            logger.info("Deepgram unavailable (no key/aiohttp); using local STT")
            return await self._fallback(audio_data, local_fallback)
        try:
            session = await self._ensure_session()
            async with session.post(
                f"{self.base_url}/listen", params=self.stt_settings, data=audio_data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    alts = (
                        result.get("results", {})
                        .get("channels", [{}])[0]
                        .get("alternatives", [{}])
                    )
                    return alts[0].get("transcript", "") if alts else ""
                logger.error(f"Deepgram error {resp.status}: {await resp.text()}")
        except Exception as e:
            logger.error(f"Deepgram STT error: {e}")
        return await self._fallback(audio_data, local_fallback)

    async def _fallback(self, audio_data: bytes, fn) -> str:
        if fn is not None:
            result = fn(audio_data)
            if hasattr(result, "__await__"):
                result = await result
            return result or ""
        return ""

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None


class OmniVoiceTTSProvider:
    """Opt-in LOCAL premium TTS via a running OmniVoice Studio instance.

    Talks to OmniVoice's OpenAI-compatible ``POST /v1/audio/speech`` endpoint on
    localhost. Audio never leaves the machine and no API key is used. Inactive
    unless the local server is reachable; every call degrades to the local
    fallback. HTTP-only integration with a separate AGPL process keeps this
    project free of AGPL obligations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.base_url = (
            config.get("base_url")
            or os.getenv(OMNIVOICE_ENV_URL)
            or OMNIVOICE_DEFAULT_URL
        ).rstrip("/")
        self.model = config.get("model", "tts-1")
        self.voice = config.get("voice", "alloy")
        self.response_format = config.get("response_format", "wav")
        self.timeout_s = config.get("timeout_s", 60)
        self._session = None

    @property
    def available(self) -> bool:
        # Local server presence is verified per-call; only the client lib is
        # required to consider this provider usable.
        return _probe_aiohttp()

    async def _ensure_session(self):
        import aiohttp

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s, connect=5)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def synthesize(
        self,
        text: str,
        local_fallback: Optional[Callable[[str], Awaitable[bytes]]] = None,
        voice_config: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Return audio bytes from local OmniVoice, else the local fallback."""
        if not self.available:
            logger.info("OmniVoice unavailable (no aiohttp); using local TTS")
            return await self._fallback(text, local_fallback)
        try:
            session = await self._ensure_session()
            cfg = voice_config or {}
            payload = {
                "model": cfg.get("model", self.model),
                "voice": cfg.get("voice", self.voice),
                "input": text,
                "response_format": cfg.get("response_format", self.response_format),
            }
            async with session.post(
                f"{self.base_url}/audio/speech", json=payload
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.error(
                    f"OmniVoice TTS error {resp.status}: {await resp.text()}"
                )
        except Exception as e:
            logger.info(f"OmniVoice TTS unreachable ({e}); using local TTS")
        return await self._fallback(text, local_fallback)

    async def _fallback(self, text: str, fn) -> bytes:
        if fn is not None:
            result = fn(text)
            if hasattr(result, "__await__"):
                result = await result
            return result or b""
        return b""

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None


class OmniVoiceSTTProvider:
    """Opt-in LOCAL premium STT via a running OmniVoice Studio instance.

    Talks to OmniVoice's OpenAI-compatible ``POST /v1/audio/transcriptions``
    endpoint on localhost. Audio never leaves the machine and no API key is
    used. Inactive unless the local server is reachable; every call degrades to
    the local fallback.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self.base_url = (
            config.get("base_url")
            or os.getenv(OMNIVOICE_ENV_URL)
            or OMNIVOICE_DEFAULT_URL
        ).rstrip("/")
        self.model = config.get("model", "whisper-1")
        self.timeout_s = config.get("timeout_s", 120)
        self._session = None

    @property
    def available(self) -> bool:
        return _probe_aiohttp()

    async def _ensure_session(self):
        import aiohttp

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s, connect=5)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def transcribe(
        self,
        audio_data: bytes,
        local_fallback: Optional[Callable[[bytes], Awaitable[str]]] = None,
    ) -> str:
        """Return a transcript from local OmniVoice, else the local fallback."""
        if not self.available:
            logger.info("OmniVoice unavailable (no aiohttp); using local STT")
            return await self._fallback(audio_data, local_fallback)
        try:
            import aiohttp

            session = await self._ensure_session()
            form = aiohttp.FormData()
            form.add_field("model", self.model)
            form.add_field(
                "file", audio_data, filename="audio.wav", content_type="audio/wav"
            )
            async with session.post(
                f"{self.base_url}/audio/transcriptions", data=form
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("text", "")
                logger.error(
                    f"OmniVoice STT error {resp.status}: {await resp.text()}"
                )
        except Exception as e:
            logger.info(f"OmniVoice STT unreachable ({e}); using local STT")
        return await self._fallback(audio_data, local_fallback)

    async def _fallback(self, audio_data: bytes, fn) -> str:
        if fn is not None:
            result = fn(audio_data)
            if hasattr(result, "__await__"):
                result = await result
            return result or ""
        return ""

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
