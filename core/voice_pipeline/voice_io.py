"""
Voice I/O Facade (pluggable STT/TTS)
====================================
"""

from __future__ import annotations

from typing import Optional


def _probe_faster_whisper() -> bool:
    try:
        __import__("faster_whisper")
        return True
    except Exception:
        return False


def _probe_openai_whisper() -> bool:
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

    def __init__(self, language: str = "en", model_size: str = "tiny") -> None:
        self.language = language
        self.model_size = model_size
        self._faster = _probe_faster_whisper()
        self._openai = _probe_openai_whisper()
        self._has_stt = self._faster or self._openai
        self._has_tts = _probe_tts()
        self._whisper_model = None
        self._backend: Optional[str] = None

    def stt_available(self) -> bool:
        return self._has_stt

    def tts_available(self) -> bool:
        return self._has_tts

    def _load_whisper(self, *, force_cpu: bool = False):
        if self._whisper_model is not None and not force_cpu:
            return self._whisper_model
        if force_cpu:
            self._whisper_model = None
            self._backend = None
        if self._faster:
            from faster_whisper import WhisperModel

            attempts = [("cpu", "int8")]
            if not force_cpu:
                try:
                    import torch

                    if torch.cuda.is_available():
                        # float16 only on CUDA; other compute types often fail at infer
                        attempts = [("cuda", "float16"), ("cpu", "int8")]
                except Exception:
                    pass
            for device, compute in attempts:
                try:
                    self._whisper_model = WhisperModel(
                        self.model_size, device=device, compute_type=compute
                    )
                    self._backend = "faster_whisper"
                    return self._whisper_model
                except Exception:
                    continue
        if self._openai:
            import whisper

            self._whisper_model = whisper.load_model(self.model_size)
            self._backend = "openai_whisper"
            return self._whisper_model
        return None

    def speech_to_text(
        self, audio_bytes: bytes, *, language: Optional[str] = None
    ) -> str:
        if not self._has_stt:
            raise RuntimeError(
                "No STT provider available (install faster-whisper)"
            )
        try:
            import os
            import tempfile

            model = self._load_whisper()
            if model is None:
                return "[whisper unavailable]"

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                lang = language or self.language

                def _run(m):
                    if self._backend == "faster_whisper":
                        segments, _info = m.transcribe(
                            tmp_path, language=lang, beam_size=1
                        )
                        return (
                            " ".join(s.text.strip() for s in segments).strip()
                            or "[empty transcript]"
                        )
                    result = m.transcribe(tmp_path, language=lang)
                    return result.get("text", "").strip() or "[empty transcript]"

                try:
                    return _run(model)
                except Exception:
                    if self._backend == "faster_whisper":
                        m2 = self._load_whisper(force_cpu=True)
                        if m2 is not None:
                            return _run(m2)
                    return "[transcript unavailable]"
            finally:
                os.unlink(tmp_path)
        except Exception:
            return "[transcript unavailable]"

    def text_to_speech(
        self, text: str, *, voice: Optional[str] = None
    ) -> bytes:
        if not self._has_tts:
            raise RuntimeError("No TTS provider available (install coqui-tts)")
        try:
            from TTS.api import TTS
            import os
            import tempfile

            tts = TTS(
                model_name="tts_models/en/ljspeech/tacotron2-DDC",
                progress_bar=False,
            )
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                out_path = tmp.name
            tts.tts_to_file(text=text, file_path=out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            os.unlink(out_path)
            return data
        except Exception:
            return b""
