"""
Desktop voice service — neural TTS preferred, optional XTTS cloning, mic STT.

TTS priority:
  1. Coqui XTTS-v2 clone (if reference WAV set + TTS installed)
  2. edge-tts (Microsoft neural voices — natural)
  3. pyttsx3 (Windows SAPI — robotic fallback)

STT priority:
  1. faster-whisper / openai-whisper (local offline)
  2. SpeechRecognition Google cloud (fallback)

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


def _probe_faster_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _probe_openai_whisper() -> bool:
    try:
        import whisper  # noqa: F401
        return True
    except Exception:
        return False


_NVIDIA_DLL_PATH_READY = False


def _ensure_ctranslate2_cuda_dlls() -> None:
    """Put pip nvidia-*-cu12 bin dirs on PATH so CTranslate2 can LoadLibrary them.

    Packages may already be installed; Windows still won't find cublas64_12.dll
    unless these directories are visible to native LoadLibrary (PATH + add_dll_directory).
    """
    global _NVIDIA_DLL_PATH_READY
    if _NVIDIA_DLL_PATH_READY:
        return
    try:
        import os
        from pathlib import Path

        dirs: list[str] = []
        for modname in (
            "nvidia.cuda_runtime",
            "nvidia.cuda_nvrtc",
            "nvidia.cublas",
            "nvidia.cudnn",
            "nvidia.cufft",
        ):
            try:
                mod = __import__(modname, fromlist=["x"])
                root = Path(next(iter(mod.__path__)))
            except Exception:
                continue
            for cand in (root / "bin", root / "lib"):
                if cand.is_dir():
                    d = str(cand)
                    dirs.append(d)
                    try:
                        os.add_dll_directory(d)
                    except (OSError, AttributeError):
                        pass
        if dirs:
            os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get(
                "PATH", ""
            )
            # Preload so dependent LoadLibrary calls resolve on Windows
            try:
                import ctypes

                for name in ("cudart64_12.dll", "cublasLt64_12.dll", "cublas64_12.dll"):
                    for d in dirs:
                        p = Path(d) / name
                        if p.is_file():
                            ctypes.WinDLL(str(p))
                            break
            except OSError as e:
                logger.debug("CUDA DLL preload: %s", e)
        _NVIDIA_DLL_PATH_READY = True
    except Exception as e:
        logger.debug("CUDA DLL path setup skipped: %s", e)
        _NVIDIA_DLL_PATH_READY = True


class DesktopVoiceService:
    """Speak replies (clone / neural / SAPI) and capture mic input."""

    def __init__(
        self, whisper_model: str = "tiny", *, light: bool = False
    ) -> None:
        self._engine = None
        self._recognizer = None
        self._coqui = None
        self._whisper = None
        self._whisper_backend: Optional[str] = None
        self.whisper_model_name = whisper_model
        self._edge_available = _probe_edge_tts()
        self._pyttsx3_available = _probe_pyttsx3()
        if light:
            # Fast path for PWA TTS API — skip heavy Coqui/Whisper/mic probes
            self._coqui_available = False
            self._faster_whisper_available = False
            self._openai_whisper_available = False
            self._stt_available = False
        else:
            self._coqui_available = _probe_coqui()
            self._faster_whisper_available = _probe_faster_whisper()
            self._openai_whisper_available = _probe_openai_whisper()
            self._stt_available = _probe_speech_recognition()
        self._whisper_available = (
            self._faster_whisper_available or self._openai_whisper_available
        )
        self._tts_available = (
            self._edge_available
            or self._pyttsx3_available
            or self._coqui_available
        )
        # Defer mic probe — can hang for tens of seconds on some Windows setups
        self._mic_available = False
        self.speak_replies: bool = False
        self.tts_engine: str = "edge" if self._edge_available else "pyttsx3"
        self.stt_engine: str = (
            "whisper" if self._whisper_available else "google"
        )
        self.initialized = False
        self.voice_id: Optional[str] = None
        self.clone_wav: Optional[str] = None
        self.clone_language: str = "en"

    async def initialize(self, *, tts_only: bool = False) -> bool:
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

        if not tts_only and self._stt_available:
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
            # XTTS is CPML (non-commercial). Auto-ack so CLI/desktop is non-interactive.
            # See https://coqui.ai/cpml — set COQUI_TOS_AGREED=0 to force the prompt.
            if os.environ.get("COQUI_TOS_AGREED") is None:
                os.environ["COQUI_TOS_AGREED"] = "1"

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
        return (
            f"Clone voice set: {p}\n"
            "XTTS clones this speaker's timbre (any person you have a clean "
            "sample of — use only with consent). Personality modes still "
            "change reply style; they do not swap the cloned voice."
        )

    def clear_clone(self) -> None:
        self.clone_wav = None

    async def record_clone_sample(
        self,
        seconds: float = 10.0,
        output_dir: Optional[Path] = None,
    ) -> str:
        """
        Record a short mic sample for XTTS cloning.

        Speak clearly for ~6–15s (one speaker, quiet room). Returns status.
        """
        if not self._mic_available or not self._stt_available:
            return (
                "Microphone not available. Install: "
                "pip install SpeechRecognition pyaudio"
            )

        import speech_recognition as sr

        if not self._recognizer:
            self._recognizer = sr.Recognizer()

        out_dir = Path(output_dir or Path("data") / "voice_samples")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "clone_ref.wav"
        phrase_limit = max(3, int(seconds))

        def _record() -> bytes:
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(
                    source,
                    timeout=8,
                    phrase_time_limit=phrase_limit,
                )
            return audio.get_wav_data()

        try:
            wav_bytes = await asyncio.to_thread(_record)
        except Exception as e:
            return f"Record failed: {e}"

        if not wav_bytes or len(wav_bytes) < 1000:
            return "Recording too short — speak longer (aim for 6–15 seconds)."

        out_path.write_bytes(wav_bytes)
        return self.set_clone_wav(str(out_path))

    async def make_edge_demo_sample(
        self,
        voice: str = "en-US-JennyNeural",
        output_dir: Optional[Path] = None,
    ) -> str:
        """Synthesize a demo reference clip via Edge TTS (proves clone pipeline)."""
        if not self._edge_available:
            return "edge-tts not installed — cannot build demo sample."

        import edge_tts

        out_dir = Path(output_dir or Path("data") / "voice_samples")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "demo_edge_ref.mp3"
        script = (
            "Hello, this is a short voice sample for cloning. "
            "I am speaking clearly so Universal Soul can learn this voice. "
            "Please clone only voices you have permission to use."
        )

        try:
            communicate = edge_tts.Communicate(script, voice)
            await communicate.save(str(out_path))
        except Exception as e:
            return f"Demo sample failed: {e}"

        return self.set_clone_wav(str(out_path))

    def status(self) -> Dict[str, Any]:
        cloning = bool(self.clone_wav) and self._coqui_available
        engine = self.tts_engine
        if cloning:
            engine = "xtts-clone"
        stt = None
        if self._mic_available:
            if self._whisper_available:
                stt = f"whisper:{self.whisper_model_name}"
            else:
                stt = "google"
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
            "stt_engine": stt,
            "whisper_available": self._whisper_available,
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

    async def synthesize(
        self, text: str, personality: str = "friendly"
    ) -> Optional[tuple[bytes, str]]:
        """Render TTS to bytes without playing (for PWA / API).

        Returns (audio_bytes, mime_type) or None.
        Prefers XTTS clone when configured, else Edge MP3.
        """
        if not text or not text.strip():
            return None
        if not self.initialized:
            await self.initialize(tts_only=True)

        spoken = text.strip()
        if len(spoken) > 1200:
            spoken = spoken[:1197] + "..."

        if self.clone_wav and self._coqui_available:
            data = await self._synth_clone_bytes(spoken)
            if data:
                return data, "audio/wav"

        if self._edge_available:
            data = await self._synth_edge_bytes(spoken, personality)
            if data:
                return data, "audio/mpeg"

        return None

    async def _synth_clone_bytes(self, text: str) -> Optional[bytes]:
        if not await self._ensure_coqui_xtts():
            return None
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
            if not audio and not out.is_file():
                return None
            return out.read_bytes()
        except Exception as e:
            logger.warning("XTTS synth failed: %s", e)
            return None
        finally:
            try:
                out.unlink(missing_ok=True)
            except OSError:
                pass

    async def _synth_edge_bytes(
        self, text: str, personality: str
    ) -> Optional[bytes]:
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
            return Path(path).read_bytes()
        except Exception as e:
            logger.warning("Edge TTS synth failed: %s", e)
            return None
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

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

    def _ensure_whisper(self, *, force_cpu: bool = False) -> bool:
        if self._whisper is not None and not force_cpu:
            return True
        if force_cpu:
            self._whisper = None
            self._whisper_backend = None

        if self._faster_whisper_available:
            try:
                from faster_whisper import WhisperModel

                # GTX 10-series: float16 usually unsupported; int8/float32 need cuBLAS 12
                # (pip nvidia-cublas-cu12 + PATH wiring via _ensure_ctranslate2_cuda_dlls).
                attempts: list[tuple[str, str]] = [("cpu", "int8")]
                if not force_cpu:
                    try:
                        import torch

                        if torch.cuda.is_available():
                            _ensure_ctranslate2_cuda_dlls()
                            attempts = [
                                ("cuda", "float16"),
                                ("cuda", "int8"),
                                ("cuda", "float32"),
                                ("cpu", "int8"),
                            ]
                    except Exception:
                        pass
                last_err: Optional[Exception] = None
                for device, compute in attempts:
                    try:
                        self._whisper = WhisperModel(
                            self.whisper_model_name,
                            device=device,
                            compute_type=compute,
                        )
                        self._whisper_backend = "faster_whisper"
                        self.stt_engine = "whisper"
                        logger.info(
                            "Whisper STT ready (faster-whisper %s on %s/%s)",
                            self.whisper_model_name,
                            device,
                            compute,
                        )
                        return True
                    except Exception as e:
                        last_err = e
                        logger.debug(
                            "faster-whisper %s/%s failed: %s", device, compute, e
                        )
                if last_err is not None:
                    logger.warning("faster-whisper load failed: %s", last_err)
            except Exception as e:
                logger.warning("faster-whisper load failed: %s", e)

        if self._openai_whisper_available:
            try:
                import whisper

                self._whisper = whisper.load_model(self.whisper_model_name)
                self._whisper_backend = "openai_whisper"
                self.stt_engine = "whisper"
                logger.info(
                    "Whisper STT ready (openai-whisper %s)",
                    self.whisper_model_name,
                )
                return True
            except Exception as e:
                logger.warning("openai-whisper load failed: %s", e)

        return False

    def _run_whisper_transcribe(self, path: str) -> Optional[str]:
        try:
            if self._whisper_backend == "faster_whisper":
                segments, _info = self._whisper.transcribe(
                    path, language="en", beam_size=1
                )
                return " ".join(s.text.strip() for s in segments).strip()
            result = self._whisper.transcribe(path, language="en")
            return (result.get("text") or "").strip()
        except Exception as e:
            logger.warning("Whisper transcribe failed: %s", e)
            return None

    def _transcribe_wav_path(self, path: str) -> Optional[str]:
        if not self._ensure_whisper():
            return None
        text = self._run_whisper_transcribe(path)
        if text is not None:
            return text
        # Incomplete CUDA runtime (e.g. missing cublas) — fall back to CPU once
        if self._whisper_backend == "faster_whisper":
            logger.warning("Whisper GPU path failed; retrying on CPU")
            if self._ensure_whisper(force_cpu=True):
                return self._run_whisper_transcribe(path)
        return None

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

            # Prefer local Whisper when available
            if self._whisper_available:
                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                try:
                    Path(tmp).write_bytes(audio.get_wav_data())
                    text = self._transcribe_wav_path(tmp)
                    if text is not None:
                        self.stt_engine = "whisper"
                        return text
                finally:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

            try:
                self.stt_engine = "google"
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
