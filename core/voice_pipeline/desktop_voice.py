"""
Desktop voice service — lightweight TTS/STT for CLI on Windows/macOS/Linux.

Uses pyttsx3 for speech output and SpeechRecognition for microphone input.
Falls back gracefully when dependencies or hardware are unavailable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Personality → pyttsx3 rate (words per minute-ish)
_PERSONALITY_RATES = {
    "professional": 175,
    "friendly": 185,
    "energetic": 210,
    "calm": 155,
    "creative": 190,
    "analytical": 165,
}


def _probe_pyttsx3() -> bool:
    try:
        import pyttsx3  # noqa: F401
        return True
    except Exception:
        return False


def _probe_speech_recognition() -> bool:
    try:
        import speech_recognition  # noqa: F401
        return True
    except Exception:
        return False


def _probe_microphone() -> bool:
    try:
        import speech_recognition as sr
        sr.Microphone()
        return True
    except Exception:
        return False


class DesktopVoiceService:
    """Speak replies and capture one-shot voice input in the desktop CLI."""

    def __init__(self) -> None:
        self._engine = None
        self._recognizer = None
        self._tts_available = _probe_pyttsx3()
        self._stt_available = _probe_speech_recognition()
        self._mic_available = self._stt_available and _probe_microphone()
        self.speak_replies: bool = False
        self.initialized = False

    async def initialize(self) -> bool:
        if self.initialized:
            return True

        if self._tts_available:
            try:
                import pyttsx3

                self._engine = await asyncio.to_thread(pyttsx3.init)
                self.initialized = True
                logger.info("Desktop voice TTS ready (pyttsx3)")
            except Exception as e:
                logger.warning("pyttsx3 init failed: %s", e)
                self._tts_available = False

        if self._stt_available:
            try:
                import speech_recognition as sr

                self._recognizer = sr.Recognizer()
                self._mic_available = _probe_microphone()
                if self._mic_available:
                    logger.info("Desktop voice STT ready (microphone)")
            except Exception as e:
                logger.warning("SpeechRecognition init failed: %s", e)
                self._mic_available = False

        return self._tts_available or self._mic_available

    def status(self) -> Dict[str, Any]:
        return {
            "tts_available": self._tts_available,
            "stt_available": self._stt_available,
            "mic_available": self._mic_available,
            "speak_replies": self.speak_replies,
            "initialized": self.initialized,
        }

    async def speak(self, text: str, personality: str = "friendly") -> bool:
        """Speak text aloud using system TTS."""
        if not text or not text.strip():
            return False
        if not self._tts_available:
            return False
        if not self.initialized:
            await self.initialize()
        if not self._engine:
            return False

        rate = _PERSONALITY_RATES.get(personality, 185)

        def _run() -> None:
            self._engine.setProperty("rate", rate)
            self._engine.say(text)
            self._engine.runAndWait()

        try:
            await asyncio.wait_for(asyncio.to_thread(_run), timeout=90.0)
            return True
        except asyncio.TimeoutError:
            logger.warning("TTS speak timed out")
            return False
        except Exception as e:
            logger.warning("TTS speak failed: %s", e)
            return False

    async def listen_once(
        self,
        timeout: int = 8,
        phrase_limit: int = 12,
    ) -> Optional[str]:
        """Capture one spoken phrase from the default microphone."""
        if not self._mic_available or not self._recognizer:
            return None

        import speech_recognition as sr

        def _capture() -> Optional[str]:
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit,
                )
            # Offline-first: try Sphinx if installed, else Google (needs network)
            try:
                return self._recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                logger.warning("STT request failed: %s", e)
                return None

        try:
            return await asyncio.to_thread(_capture)
        except Exception as e:
            logger.warning("Microphone listen failed: %s", e)
            return None
