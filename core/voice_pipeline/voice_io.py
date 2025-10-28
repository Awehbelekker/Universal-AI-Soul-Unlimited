"""
Voice I/O Facade (pluggable STT/TTS)
====================================

Minimal voice facade with runtime provider checks.
Intended as a stable integration point; providers can be added later
without changing call sites.
"""

from __future__ import annotations

from typing import Optional


def _probe_whisper() -> bool:
    try:
        __import__("whisper")
        return True
    except Exception:
        return False


def _probe_tts() -> bool:
    # Placeholder probe; replace with your preferred local TTS
    # (e.g., Coqui TTS) in a future update
    try:
        __import__("TTS")
        return True
    except Exception:
        return False


class VoiceIO:
    """Simple voice I/O wrapper with best-effort providers."""

    def __init__(self, language: str = "en") -> None:
        self.language = language
        self._has_stt = _probe_whisper()
        self._has_tts = _probe_tts()

    def stt_available(self) -> bool:
        return self._has_stt

    def tts_available(self) -> bool:
        return self._has_tts

    def speech_to_text(
        self, audio_bytes: bytes, *, language: Optional[str] = None
    ) -> str:
        if not self._has_stt:
            raise RuntimeError(
                "No STT provider available (install whisper or similar)"
            )
        # Placeholder: integrate real whisper or vosk pipeline here
        # Return a dummy result to keep the call sites working
        return "[transcript unavailable in stub]"

    def text_to_speech(
        self, text: str, *, voice: Optional[str] = None
    ) -> bytes:
        if not self._has_tts:
            raise RuntimeError(
                "No TTS provider available (install TTS or similar)"
            )
        # Placeholder: integrate real TTS engine and return audio bytes
        return b""
