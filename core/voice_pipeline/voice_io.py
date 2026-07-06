"""
Voice I/O Facade (pluggable STT/TTS)
====================================
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
        self._whisper_model = None

    def stt_available(self) -> bool:
        return self._has_stt

    def tts_available(self) -> bool:
        return self._has_tts

    def _load_whisper(self):
        if self._whisper_model is None and self._has_stt:
            import whisper
            self._whisper_model = whisper.load_model("tiny")
        return self._whisper_model

    def speech_to_text(
        self, audio_bytes: bytes, *, language: Optional[str] = None
    ) -> str:
        if not self._has_stt:
            raise RuntimeError(
                "No STT provider available (install openai-whisper)"
            )
        try:
            import io
            import tempfile
            import os

            model = self._load_whisper()
            if model is None:
                return "[whisper unavailable]"

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                result = model.transcribe(tmp_path, language=language or self.language)
                return result.get("text", "").strip() or "[empty transcript]"
            finally:
                os.unlink(tmp_path)
        except Exception:
            return "[transcript unavailable]"

    def text_to_speech(
        self, text: str, *, voice: Optional[str] = None
    ) -> bytes:
        if not self._has_tts:
            raise RuntimeError("No TTS provider available (install TTS)")
        try:
            from TTS.api import TTS
            tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                out_path = tmp.name
            tts.tts_to_file(text=text, file_path=out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            os.unlink(out_path)
            return data
        except Exception:
            return b""
