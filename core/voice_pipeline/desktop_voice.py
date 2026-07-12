"""
Desktop voice service — neural TTS preferred, optional XTTS cloning, mic STT.

TTS priority:
  1. Coqui XTTS-v2 clone (if reference WAV set + TTS installed)
  2. edge-tts (Microsoft neural voices — natural)
  3. pyttsx3 (Windows SAPI — robotic fallback)

STT: SpeechRecognition + microphone (Google cloud by default).

Setup cloning:
  python scripts/setup_voice_clone.py
  Then in CLI: voice clone path/to/sample.wav
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_EDGE_VOICES = {
    "professional": "en-US-GuyNeural",
    "friendly": "en-US-JennyNeural",
    "energetic": "en-US-AriaNeural",
    "calm": "en-GB-SoniaNeural",
    "creative": "en-US-AnaNeural",
    "analytical": "en-US-ChristopherNeural",
}

_PERSONALITY_RATES = {
    "professional": 175,
    "friendly": 185,
    "energetic": 210,
    "calm": 155,
    "creative": 190,
    "analytical": 165,
}


def _probe_edge_tts() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def _probe_pyttsx3() -> bool:
    try:
        import pyttsx3  # noqa: F401
        return True
    except Exception:
        return False


def _probe_coqui() -> bool:
    try:
        from TTS.api import TTS  # noqa: F401
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
    """Speak replies (clone / neural / SAPI) and capture mic input."""

    def __init__(self) -> None:
        self._engine = None
        self._recognizer = None
        self._coqui = None
        self._edge_available = _probe_edge_tts()
        self._pyttsx3_available = _probe_pyttsx3()
        self._coqui_available = _probe_coqui()
        self._tts_available = (
            self._edge_available
            or self._pyttsx3_available
            or self._coqui_available
        )
        self._stt_available = _probe_speech_recognition()
        self._mic_available = self._stt_available and _probe_microphone()
        self.speak_replies: bool = False
        self.tts_engine: str = "edge" if self._edge_available else "pyttsx3"
        self.initialized = False
        self.voice_id: Optional[str] = None
        self.clone_wav: Optional[str] = None
        self.clone_language: str = "en"

    async def initialize(self) -> bool:
        if self.initialized:
            return True

        if self._edge_available:
            self.tts_engine = "edge"
            self.initialized = True
            logger.info("Desktop voice TTS ready (edge-tts neural)")
        elif self._pyttsx3_available:
            try:
                import pyttsx3

                self._engine = await asyncio.to_thread(pyttsx3.init)
                self.tts_engine = "pyttsx3"
                self.initialized = True
                logger.info("Desktop voice TTS ready (pyttsx3 fallback)")
            except Exception as e:
                logger.warning("pyttsx3 init failed: %s", e)
                self._pyttsx3_available = False

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

        self._tts_available = (
            self._edge_available
            or self._pyttsx3_available
            or self._coqui_available
        )
        self.initialized = self.initialized or self._tts_available
        return self._tts_available or self._mic_available

    async def _ensure_coqui_xtts(self) -> bool:
        if not self._coqui_available:
            return False
        if self._coqui and getattr(self._coqui, "initialized", False):
            return True
        try:
            from core.engines.coqui_tts_optimizer import CoquiTTSOptimizer

            use_gpu = False
            try:
                import torch

                use_gpu = bool(torch.cuda.is_available())
            except Exception:
                pass

            self._coqui = CoquiTTSOptimizer(
                model_name=CoquiTTSOptimizer.xtts_model_name(),
                use_gpu=use_gpu,
            )
            ok = await self._coqui.initialize()
            if ok:
                logger.info("XTTS-v2 ready for voice cloning (gpu=%s)", use_gpu)
            return ok
        except Exception as e:
            logger.warning("XTTS init failed: %s", e)
            return False

    def set_clone_wav(self, path: str) -> str:
        """Register a reference WAV for cloning. Returns status message."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"File not found: {p}"
        if p.suffix.lower() not in (".wav", ".mp3", ".flac", ".ogg"):
            return "Use a short audio file (.wav preferred, 6–15 seconds)."
        self.clone_wav = str(p)
        if not self._coqui_available:
            return (
                f"Reference saved: {p}\n"
                "Coqui TTS not installed yet. Run:\n"
                "  python scripts/setup_voice_clone.py\n"
                "Then restart and use 'voice' — cloning will activate."
            )
        return f"Clone voice set: {p}"

    def clear_clone(self) -> None:
        self.clone_wav = None

    def status(self) -> Dict[str, Any]:
        cloning = bool(self.clone_wav) and self._coqui_available
        engine = self.tts_engine
        if cloning:
            engine = "xtts-clone"
        return {
            "tts_available": self._tts_available,
            "tts_engine": engine if self._tts_available else None,
            "edge_available": self._edge_available,
            "pyttsx3_available": self._pyttsx3_available,
            "coqui_available": self._coqui_available,
            "voice_id": self.voice_id or _EDGE_VOICES.get("friendly"),
            "clone_wav": self.clone_wav,
            "cloning": cloning,
            "stt_available": self._stt_available,
            "mic_available": self._mic_available,
            "speak_replies": self.speak_replies,
            "initialized": self.initialized,
            "note": (
                f"Cloning from {self.clone_wav}"
                if cloning
                else (
                    "Neural Edge TTS active"
                    if self.tts_engine == "edge"
                    else "Robotic pyttsx3 — install edge-tts. "
                    "For cloning: python scripts/setup_voice_clone.py "
                    "then 'voice clone sample.wav'"
                )
            ),
        }

    async def speak(self, text: str, personality: str = "friendly") -> bool:
        """Speak text aloud using best available TTS."""
        if not text or not text.strip():
            return False
        if not self._tts_available and not self._coqui_available:
            return False
        if not self.initialized:
            await self.initialize()

        spoken = text.strip()
        if len(spoken) > 1200:
            spoken = spoken[:1197] + "..."

        if self.clone_wav and self._coqui_available:
            ok = await self._speak_clone(spoken)
            if ok:
                return True
            logger.warning("Clone speak failed — falling back")

        if self._edge_available:
            ok = await self._speak_edge(spoken, personality)
            if ok:
                return True
            logger.warning("Edge TTS failed — trying pyttsx3 fallback")

        if self._pyttsx3_available:
            return await self._speak_pyttsx3(spoken, personality)

        return False

    async def _speak_clone(self, text: str) -> bool:
        if not await self._ensure_coqui_xtts():
            return False
        assert self.clone_wav
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        out = Path(tmp)
        try:
            audio = await self._coqui.clone_speak(
                text=text,
                speaker_wav=self.clone_wav,
                output_path=out,
                language=self.clone_language,
            )
            if not audio:
                return False
            await self._play_audio_file(str(out))
            return True
        except Exception as e:
            logger.warning("XTTS clone speak failed: %s", e)
            return False
        finally:
            try:
                out.unlink(missing_ok=True)
            except OSError:
                pass

    async def _speak_edge(self, text: str, personality: str) -> bool:
        import edge_tts

        voice = self.voice_id or _EDGE_VOICES.get(
            personality, _EDGE_VOICES["friendly"]
        )
        rate = {
            "energetic": "+15%",
            "calm": "-10%",
            "professional": "+0%",
            "friendly": "+5%",
            "creative": "+8%",
            "analytical": "-5%",
        }.get(personality, "+0%")

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(path)
            await self._play_audio_file(path)
            return True
        except Exception as e:
            logger.warning("Edge TTS speak failed: %s", e)
            return False
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    async def _speak_pyttsx3(self, text: str, personality: str) -> bool:
        if not self._engine:
            try:
                import pyttsx3

                self._engine = await asyncio.to_thread(pyttsx3.init)
            except Exception as e:
                logger.warning("pyttsx3 init failed: %s", e)
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

    async def _play_audio_file(self, path: str) -> None:
        abs_path = str(Path(path).resolve())

        if os.name == "nt":
            escaped = abs_path.replace("'", "''")
            script = (
                "Add-Type -AssemblyName presentationCore; "
                "$m = New-Object System.Windows.Media.MediaPlayer; "
                f"$m.Open([uri]'{escaped}'); "
                "$m.Play(); "
                "while (-not $m.NaturalDuration.HasTimeSpan) "
                "{ Start-Sleep -Milliseconds 40 }; "
                "Start-Sleep -Milliseconds "
                "([int]($m.NaturalDuration.TimeSpan.TotalMilliseconds) + 200); "
                "$m.Close()"
            )

            def _play() -> None:
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        script,
                    ],
                    check=False,
                    capture_output=True,
                    timeout=180,
                )

            await asyncio.to_thread(_play)
            return

        for cmd in (
            ["afplay", abs_path],
            ["ffplay", "-nodisp", "-autoexit", abs_path],
            ["mpg123", abs_path],
        ):
            try:
                await asyncio.to_thread(
                    subprocess.run, cmd, check=True, capture_output=True, timeout=180
                )
                return
            except Exception:
                continue
        raise RuntimeError("No audio player available")

    async def listen_once(
        self,
        timeout: int = 8,
        phrase_limit: int = 12,
    ) -> Optional[str]:
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
