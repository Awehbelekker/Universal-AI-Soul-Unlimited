"""
Desktop voice service — neural TTS preferred, mic STT for CLI.

TTS priority:
  1. edge-tts (Microsoft neural voices — natural)
  2. pyttsx3 (Windows SAPI — robotic fallback)

STT: SpeechRecognition + microphone (Google cloud by default).

True voice cloning (Coqui XTTS-v2) is not wired yet — needs Coqui TTS
install + a short reference WAV. See PROJECT_STATUS.md.
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

# Personality → Edge neural voice
_EDGE_VOICES = {
    "professional": "en-US-GuyNeural",
    "friendly": "en-US-JennyNeural",
    "energetic": "en-US-AriaNeural",
    "calm": "en-GB-SoniaNeural",
    "creative": "en-US-AnaNeural",
    "analytical": "en-US-ChristopherNeural",
}

# Personality → pyttsx3 rate (fallback)
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
    """Speak replies (neural when possible) and capture mic input."""

    def __init__(self) -> None:
        self._engine = None
        self._recognizer = None
        self._edge_available = _probe_edge_tts()
        self._pyttsx3_available = _probe_pyttsx3()
        self._tts_available = self._edge_available or self._pyttsx3_available
        self._stt_available = _probe_speech_recognition()
        self._mic_available = self._stt_available and _probe_microphone()
        self.speak_replies: bool = False
        self.tts_engine: str = "edge" if self._edge_available else "pyttsx3"
        self.initialized = False
        self.voice_id: Optional[str] = None  # override Edge voice name

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

        self._tts_available = self._edge_available or self._pyttsx3_available
        return self._tts_available or self._mic_available

    def status(self) -> Dict[str, Any]:
        return {
            "tts_available": self._tts_available,
            "tts_engine": self.tts_engine if self._tts_available else None,
            "edge_available": self._edge_available,
            "pyttsx3_available": self._pyttsx3_available,
            "voice_id": self.voice_id or _EDGE_VOICES.get("friendly"),
            "stt_available": self._stt_available,
            "mic_available": self._mic_available,
            "speak_replies": self.speak_replies,
            "initialized": self.initialized,
            "cloning": False,
            "note": (
                "Neural Edge TTS active"
                if self.tts_engine == "edge"
                else "Robotic pyttsx3 — install edge-tts for natural voice. "
                "Voice cloning (XTTS) not enabled yet."
            ),
        }

    async def speak(self, text: str, personality: str = "friendly") -> bool:
        """Speak text aloud using best available TTS."""
        if not text or not text.strip():
            return False
        if not self._tts_available:
            return False
        if not self.initialized:
            await self.initialize()

        # Keep spoken replies snappy
        spoken = text.strip()
        if len(spoken) > 1200:
            spoken = spoken[:1197] + "..."

        if self._edge_available and self.tts_engine == "edge":
            ok = await self._speak_edge(spoken, personality)
            if ok:
                return True
            logger.warning("Edge TTS failed — trying pyttsx3 fallback")

        if self._pyttsx3_available:
            return await self._speak_pyttsx3(spoken, personality)

        return False

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
        """Play an audio file on Windows (MediaPlayer) or via afplay/ffplay."""
        abs_path = str(Path(path).resolve())

        if os.name == "nt":
            # PowerShell WPF MediaPlayer — supports mp3, no extra deps
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
                    timeout=120,
                )

            await asyncio.to_thread(_play)
            return

        # macOS / Linux best-effort
        for cmd in (
            ["afplay", abs_path],
            ["ffplay", "-nodisp", "-autoexit", abs_path],
            ["mpg123", abs_path],
        ):
            try:
                await asyncio.to_thread(
                    subprocess.run, cmd, check=True, capture_output=True, timeout=120
                )
                return
            except Exception:
                continue
        raise RuntimeError("No audio player available for Edge TTS output")

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
