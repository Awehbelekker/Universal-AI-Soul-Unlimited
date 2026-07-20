"""
Desktop voice service — neural TTS preferred, optional XTTS cloning, mic STT.

TTS priority:
  1. Coqui XTTS-v2 clone (if reference WAV set + TTS installed)
  2. edge-tts (Microsoft neural voices — natural, needs network)
  3. Local neural TTS (Coqui single-speaker, fully offline — zero network)
  4. pyttsx3 (Windows SAPI — robotic fallback)

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
    "creative": "en-US-AvaNeural",
    "analytical": "en-US-ChristopherNeural",
}

# Curated neural voices for PWA / Settings (Edge TTS).
_VOICE_CATALOG = [
    {"id": "auto", "label": "Auto (match tone)"},
    {"id": "en-US-EmmaMultilingualNeural", "label": "Emma (warm multilingual)"},
    {"id": "en-US-JennyNeural", "label": "Jenny (friendly US)"},
    {"id": "en-US-AriaNeural", "label": "Aria (expressive)"},
    {"id": "en-US-AvaNeural", "label": "Ava (bright)"},
    {"id": "en-US-AndrewNeural", "label": "Andrew (natural male)"},
    {"id": "en-US-GuyNeural", "label": "Guy (professional)"},
    {"id": "en-US-ChristopherNeural", "label": "Christopher (clear)"},
    {"id": "en-GB-SoniaNeural", "label": "Sonia (calm UK)"},
    {"id": "en-AU-NatashaNeural", "label": "Natasha (AU)"},
    {"id": "en-ZA-LeahNeural", "label": "Leah (ZA)"},
]

# Edge-tts prosody: rate like "+5%", pitch like "+2Hz", volume like "+0%".
_PERSONALITY_PROSODY = {
    "professional": {"rate": "+0%", "pitch": "-2Hz", "volume": "+0%"},
    "friendly": {"rate": "+3%", "pitch": "+0Hz", "volume": "+0%"},
    "energetic": {"rate": "+12%", "pitch": "+4Hz", "volume": "+5%"},
    "calm": {"rate": "-12%", "pitch": "-4Hz", "volume": "-5%"},
    "creative": {"rate": "+6%", "pitch": "+2Hz", "volume": "+0%"},
    "analytical": {"rate": "-5%", "pitch": "-3Hz", "volume": "+0%"},
}

_PERSONALITY_RATES = {
    "professional": 175,
    "friendly": 185,
    "energetic": 210,
    "calm": 155,
    "creative": 190,
    "analytical": 165,
}

# Local single-speaker neural TTS model (fully offline once downloaded — no
# reference WAV and no network at synth time). Used as the high-quality offline
# default when edge-tts is unavailable/offline and XTTS cloning isn't set up.
# Override with the SOUL_LOCAL_TTS_MODEL env var.
_LOCAL_TTS_MODEL = os.environ.get(
    "SOUL_LOCAL_TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC"
)

# Kokoro-82M — natural, low-latency, fully-offline neural TTS. Voices are
# Apache-2.0 built-ins (no cloning). The id prefix encodes accent+gender:
# a*=American, b*=British; *f*=female, *m*=male. lang_code is the first char.
_KOKORO_SAMPLE_RATE = 24000
_KOKORO_DEFAULT_VOICE = os.environ.get("SOUL_KOKORO_VOICE", "af_heart")
_KOKORO_CATALOG = [
    {"id": "af_heart", "label": "Heart (warm US female)"},
    {"id": "af_bella", "label": "Bella (bright US female)"},
    {"id": "af_nicole", "label": "Nicole (soft US female)"},
    {"id": "am_michael", "label": "Michael (natural US male)"},
    {"id": "am_puck", "label": "Puck (characterful US male)"},
    {"id": "am_onyx", "label": "Onyx (deep US male)"},
    {"id": "bf_emma", "label": "Emma (UK female)"},
    {"id": "bm_george", "label": "George (mature UK male)"},
    {"id": "bm_fable", "label": "Fable (cinematic UK male)"},
]


def voice_catalog() -> list:
    """Public list of Edge voices for Settings UI."""
    return list(_VOICE_CATALOG)


def kokoro_voice_catalog() -> list:
    """Public list of Kokoro voices for Settings UI."""
    return list(_KOKORO_CATALOG)


def prepare_speech_text(text: str) -> str:
    """Strip chat markup / tool dumps so neural TTS stays natural."""
    import re

    s = (text or "").strip()
    if not s:
        return ""
    # Drop fenced code and inline code
    s = re.sub(r"```[\s\S]*?```", " ", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    # Drop leaked system / tool scaffolding (whole lines)
    s = re.sub(
        r"(?im)^(tool result|deep thinkmesh|shared memory|ground truth|"
        r"you are |speak in a |prefer concise|"
        r"you have pc-side tools|available tools:|"
        r"do not invent|prefer tools for).*$",
        " ",
        s,
    )
    # Drop TOOL directives and JSON leftovers
    s = re.sub(r"(?is)\bTOOL\s*:\s*\{.*?\}", " ", s)
    s = re.sub(r"(?is)\{[^{}]{0,800}\}", " ", s)
    s = re.sub(r"^\s*[\{\}\[\]\",]+\s*", " ", s)
    s = re.sub(r"\*+([^*]+)\*+", r"\1", s)
    s = re.sub(r"_+([^_]+)_+", r"\1", s)
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*[-*•]\s+", "", s, flags=re.MULTILINE)
    # Never let URL / markup reach TTS (Edge otherwise reads "http slash slash…")
    s = re.sub(r"(?is)<speak\b[^>]*>.*?</speak>", " ", s)
    s = re.sub(r"(?is)</?(speak|voice|break|prosody|emphasis)\b[^>]*>", " ", s)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"\bwww\.\S+", " ", s)
    s = re.sub(r"\b[\w.-]+\.(com|org|net|io|dev|ai|html?|php|aspx)\b\S*", " ", s, flags=re.I)
    s = re.sub(r"\b[\w.+-]+@[\w.-]+\.\w+\b", " ", s)
    s = re.sub(r"[⚙✅❌⚠→←↑↓★☆•\|]+", " ", s)
    # Remove sentences that are clearly tool/prompt leakage
    chunks = re.split(r"(?<=[.!?])\s+", s)
    keep = []
    bad = re.compile(
        r"(?i)\b("
        r"pc-side tools|available tools|tool result|web_search|"
        r"ground truth|thinkmesh|num_predict|ollama|"
        r"ending your reply with|exactly:\s*tool"
        r")\b"
    )
    for c in chunks:
        c = c.strip()
        if not c or bad.search(c):
            continue
        keep.append(c)
    s = " ".join(keep) if keep else ""
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def spoken_excerpt(text: str, max_chars: int = 220) -> str:
    """Pick a short spoken line from a chat reply (never a doc dump)."""
    import re

    s = prepare_speech_text(text)
    if not s:
        return ""
    # Reject filler / dump leftovers
    if len(s) > 100 and not re.search(r"[.!?]", s):
        return ""
    if re.search(r"(.)\1{12,}", s):
        s = re.sub(r"(.)\1{12,}", r"\1\1\1", s)
    dumpish = (
        s.count("\n") >= 4
        or s.count("|") >= 3
        or s.lower().startswith(("error:", "http", "get ", "post "))
        or len(re.findall(r"\d+\.\s", s)) >= 3
        or (len(s.split()) > 60 and s.count(".") < 2)
    )
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", s) if p.strip()]
    if not parts:
        return clip_for_speech(s, max_chars=max_chars) if not dumpish else ""
    # Always prefer a single clear sentence for voice
    out = parts[0]
    if (
        not dumpish
        and len(parts) > 1
        and len(out) < 90
        and len(out) + len(parts[1]) < max_chars
    ):
        out = f"{out} {parts[1]}"
    out = clip_for_speech(out, max_chars=max_chars)
    if len(out) > 40 and len(set(out.lower().split())) < 4:
        return ""
    # Reject leftover punctuation/JSON crumbs
    if re.fullmatch(r"[\W\d_]{0,40}", out or ""):
        return ""
    return out


def spoken_passage(text: str, max_chars: int = 480) -> str:
    """Multi-sentence speakable version of a chat reply (reads most of what was written)."""
    import re

    s = prepare_speech_text(text)
    if not s:
        return ""
    max_chars = max(120, int(max_chars))
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", s) if p.strip()]
    if not parts:
        return clip_for_speech(s, max_chars=max_chars)
    # Longer library summaries: allow more sentences when budget is high
    max_sentences = 10 if max_chars <= 800 else min(48, max(12, max_chars // 60))
    kept: list[str] = []
    total = 0
    for part in parts:
        add = len(part) + (1 if kept else 0)
        if kept and total + add > max_chars:
            break
        kept.append(part)
        total += add
        if len(kept) >= max_sentences:
            break
    if not kept:
        return clip_for_speech(parts[0], max_chars=max_chars)
    return clip_for_speech(" ".join(kept), max_chars=max_chars)


def speech_for_tts(text: str, max_chars: int = 420) -> str:
    """Pick excerpt vs multi-sentence passage based on speak budget."""
    max_chars = max(60, int(max_chars))
    if max_chars >= 280:
        return spoken_passage(text, max_chars=max_chars)
    return spoken_excerpt(text, max_chars=max_chars)


_GREETING_RE = None


def is_simple_greeting(message: str) -> bool:
    import re

    global _GREETING_RE
    if _GREETING_RE is None:
        _GREETING_RE = re.compile(
            r"^\s*(hi|hii+|hello|hey|yo|howdy|good\s*(morning|afternoon|evening)|"
            r"sup|hiya|heya)([\s,.!?]|$)",
            re.I,
        )
    return bool(_GREETING_RE.match((message or "").strip()))


def greeting_speak_line(companion: str = "Soul") -> str:
    name = (companion or "Soul").strip() or "Soul"
    return f"Hey, I'm {name}. Good to hear from you."


def clip_for_speech(text: str, max_chars: int = 420) -> str:
    """Keep spoken replies short so voice stays snappy (chat shows full text)."""
    import re

    s = prepare_speech_text(text)
    if not s:
        return ""
    max_chars = max(60, int(max_chars))
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    m = list(re.finditer(r"[.!?]\s", cut))
    if m and m[-1].end() > max_chars * 0.4:
        cut = cut[: m[-1].end()].strip()
    else:
        sp = cut.rfind(" ")
        if sp > max_chars * 0.45:
            cut = cut[:sp].strip()
        cut = cut.rstrip(",;:-") + "…"
    return cut


def detect_speech_emotion(text: str) -> str:
    """Lightweight cue from reply text → excited | warm | serious | gentle | neutral."""
    import re

    t = (text or "").lower()
    if not t:
        return "neutral"
    bangs = t.count("!")
    if bangs >= 2 or re.search(
        r"\b(amazing|awesome|congrats|congratulations|woohoo|excited|fantastic)\b",
        t,
    ):
        return "excited"
    if re.search(r"\b(sorry|unfortunately|careful|warning|important|serious)\b", t):
        return "serious"
    if re.search(r"\b(gentle|softly|breathe|calm|peace|rest|quiet)\b", t):
        return "gentle"
    if re.search(
        r"\b(love|glad|happy|warm|care|here for you|proud of you)\b", t
    ) or ("?" in t and bangs == 0):
        return "warm"
    return "neutral"


_EMOTION_BIAS = {
    "excited": {"rate": 8, "pitch": 3},
    "warm": {"rate": 0, "pitch": 1},
    "serious": {"rate": -4, "pitch": -2},
    "gentle": {"rate": -6, "pitch": -1},
    "neutral": {"rate": 0, "pitch": 0},
}

# Storyteller: slight character shift of the parent's own clone (never celebrity labels).
STORYTELLER_RATE_BIAS = -8  # a touch slower for bedtime
STORYTELLER_PITCH_BIAS = 5  # Edge path
STORYTELLER_WAV_RATE_FACTOR = 1.07  # mild higher pitch+tempo on clone WAV


def storyteller_shift_wav(
    wav_bytes: bytes, *, rate_factor: float = STORYTELLER_WAV_RATE_FACTOR
) -> bytes:
    """Mild pitch/tempo shift on a WAV so the parent's clone sounds distinct.

    Uses frame-rate rewrite (no celebrity models). Safe no-op on bad input.
    """
    import io
    import wave

    if not wav_bytes or len(wav_bytes) < 44:
        return wav_bytes
    factor = float(rate_factor or 1.0)
    if abs(factor - 1.0) < 0.01:
        return wav_bytes
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as src:
            params = src.getparams()
            frames = src.readframes(src.getnframes())
            rate = src.getframerate()
        new_rate = max(8000, min(96000, int(rate * factor)))
        out = io.BytesIO()
        with wave.open(out, "wb") as dst:
            dst.setparams(params)
            dst.setframerate(new_rate)
            dst.writeframes(frames)
        return out.getvalue()
    except Exception:
        return wav_bytes


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text_to_edge_ssml(text: str, voice: str) -> str:
    """Wrap multi-sentence speech in SSML with short breath breaks.

    Short lines stay plain (caller should skip SSML) — breaks only when useful.
    """
    import re

    clean = prepare_speech_text(text)
    if not clean:
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", clean) if p.strip()]
    if len(parts) <= 1:
        return ""  # signal: use plain text
    chunks: list[str] = []
    for i, part in enumerate(parts):
        chunks.append(_xml_escape(part))
        if i < len(parts) - 1:
            ms = 280 if part.endswith(("!", "?")) else 200
            chunks.append(f'<break time="{ms}ms"/>')
    body = " ".join(chunks)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US">'
        f'<voice name="{_xml_escape(voice)}">{body}</voice></speak>'
    )


def _clamp_rate(pct: int) -> str:
    pct = max(-50, min(100, int(pct)))
    return f"{pct:+d}%"


def _clamp_pitch(hz: int) -> str:
    hz = max(-50, min(50, int(hz)))
    return f"{hz:+d}Hz"


def _clamp_volume(pct: int) -> str:
    pct = max(-50, min(50, int(pct)))
    return f"{pct:+d}%"


def resolve_prosody(
    personality: str = "friendly",
    *,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    volume: Optional[str] = None,
    rate_bias: Optional[int] = None,
    pitch_bias: Optional[int] = None,
    emotion: Optional[str] = None,
) -> Dict[str, str]:
    """Merge personality defaults with optional overrides / slider / emotion biases."""
    base = dict(
        _PERSONALITY_PROSODY.get(personality, _PERSONALITY_PROSODY["friendly"])
    )
    emo = _EMOTION_BIAS.get(emotion or "neutral", _EMOTION_BIAS["neutral"])
    rb = int(rate_bias or 0) + int(emo.get("rate", 0))
    pb = int(pitch_bias or 0) + int(emo.get("pitch", 0))
    apply_rate = rate is not None or rate_bias is not None or bool(emo.get("rate"))
    apply_pitch = pitch is not None or pitch_bias is not None or bool(emo.get("pitch"))

    if rate:
        base["rate"] = rate if str(rate).endswith("%") else _clamp_rate(int(rate))
    elif apply_rate:
        try:
            cur = int(str(base["rate"]).replace("%", "").replace("+", "") or "0")
        except ValueError:
            cur = 0
        base["rate"] = _clamp_rate(cur + rb)
    if pitch:
        p = str(pitch)
        base["pitch"] = p if p.endswith("Hz") else _clamp_pitch(int(p))
    elif apply_pitch:
        try:
            cur = int(str(base["pitch"]).replace("Hz", "").replace("+", "") or "0")
        except ValueError:
            cur = 0
        base["pitch"] = _clamp_pitch(cur + pb)
    if volume:
        v = str(volume)
        base["volume"] = v if v.endswith("%") else _clamp_volume(int(v))
    return base


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


def _probe_kokoro() -> bool:
    try:
        from kokoro import KPipeline  # noqa: F401
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
        self._local_tts = None
        self._kokoro = None
        self._whisper = None
        self._whisper_backend: Optional[str] = None
        self.whisper_model_name = whisper_model
        self._edge_available = _probe_edge_tts()
        self._pyttsx3_available = _probe_pyttsx3()
        # Kokoro is light to probe (import only) and is the natural offline
        # default for the PWA, so probe it even in light mode.
        self._kokoro_available = _probe_kokoro()
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
        # Local neural TTS uses the same Coqui package; available whenever Coqui
        # imports (no reference WAV needed, unlike XTTS cloning).
        self._local_tts_available = self._coqui_available
        self._whisper_available = (
            self._faster_whisper_available or self._openai_whisper_available
        )
        self._tts_available = (
            self._edge_available
            or self._pyttsx3_available
            or self._coqui_available
            or self._kokoro_available
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
        # Slider biases (added on top of personality prosody). None = pure tone map.
        self.rate_bias: int = 0
        self.pitch_bias: int = 0
        self.volume_override: Optional[str] = None

    async def initialize(self, *, tts_only: bool = False) -> bool:
        if self.initialized:
            return True

        if self._edge_available:
            self.tts_engine = "edge"
            self.initialized = True
            logger.info("Desktop voice TTS ready (edge-tts neural)")
        elif self._kokoro_available:
            # Natural offline default when Edge is unavailable — loads lazily.
            self.tts_engine = "kokoro"
            self.initialized = True
            logger.info("Desktop voice TTS ready (Kokoro-82M, offline)")
        elif self._local_tts_available:
            # Offline neural default — model loads lazily on first synth.
            self.tts_engine = "local-neural"
            self.initialized = True
            logger.info("Desktop voice TTS ready (local neural, offline)")
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
            or self._kokoro_available
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

    async def _ensure_local_tts(self) -> bool:
        """Load a local single-speaker neural model (offline, no reference WAV).

        Reuses CoquiTTSOptimizer with a plain single-speaker model so no
        speaker_wav is required at synth time. The model downloads once on
        first use, then runs fully offline — the zero-network default.
        """
        if not self._local_tts_available:
            return False
        if self._local_tts and getattr(self._local_tts, "initialized", False):
            return True
        try:
            if os.environ.get("COQUI_TOS_AGREED") is None:
                os.environ["COQUI_TOS_AGREED"] = "1"

            from core.engines.coqui_tts_optimizer import CoquiTTSOptimizer

            use_gpu = False
            try:
                import torch

                use_gpu = bool(torch.cuda.is_available())
            except Exception:
                pass

            self._local_tts = CoquiTTSOptimizer(
                model_name=_LOCAL_TTS_MODEL,
                use_gpu=use_gpu,
            )
            ok = await self._local_tts.initialize()
            if ok:
                logger.info(
                    "Local neural TTS ready (%s, gpu=%s)",
                    _LOCAL_TTS_MODEL,
                    use_gpu,
                )
            return ok
        except Exception as e:
            logger.warning("Local TTS init failed: %s", e)
            return False

    async def _synth_local_bytes(self, text: str, personality: str) -> Optional[bytes]:
        """Render offline neural TTS to WAV bytes (no network, no clone WAV)."""
        if not await self._ensure_local_tts():
            return None
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        out = Path(tmp)
        try:
            audio = await self._local_tts.synthesize(
                text=text,
                personality=personality,
                output_path=out,
            )
            if not audio and not out.is_file():
                return None
            return out.read_bytes()
        except Exception as e:
            logger.warning("Local TTS synth failed: %s", e)
            return None
        finally:
            try:
                out.unlink(missing_ok=True)
            except OSError:
                pass

    def _resolve_kokoro_voice(self, voice_id: Optional[str] = None) -> str:
        """Map a requested voice id to a valid Kokoro voice, else the default."""
        candidate = voice_id if voice_id is not None else self.voice_id
        if candidate and str(candidate).lower() not in ("auto", "default", "tone"):
            valid = {v["id"] for v in _KOKORO_CATALOG}
            if str(candidate) in valid:
                return str(candidate)
        return _KOKORO_DEFAULT_VOICE

    async def _ensure_kokoro(self) -> bool:
        """Load the Kokoro KPipeline once (CUDA if available, else CPU)."""
        if not self._kokoro_available:
            return False
        if self._kokoro is not None:
            return True
        try:
            from kokoro import KPipeline

            device = "cpu"
            try:
                import torch

                if torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                pass

            # lang_code 'a' = American English; British voices (b*) still render
            # acceptably. A single pipeline covers the full built-in catalog.
            self._kokoro = await asyncio.to_thread(
                KPipeline, lang_code="a", device=device
            )
            logger.info("Kokoro-82M ready (device=%s)", device)
            return True
        except Exception as e:
            logger.warning("Kokoro init failed: %s", e)
            self._kokoro = None
            return False

    async def _synth_kokoro_bytes(
        self, text: str, voice_id: Optional[str] = None
    ) -> Optional[bytes]:
        """Render natural offline Kokoro TTS to 24k mono PCM16 WAV bytes."""
        if not await self._ensure_kokoro():
            return None
        voice = self._resolve_kokoro_voice(voice_id)

        def _run() -> Optional[bytes]:
            import io

            import numpy as np
            import soundfile as sf

            segments = [
                audio
                for _, _, audio in self._kokoro(
                    text, voice=voice, split_pattern=r"(?<=[.!?])\s+"
                )
            ]
            if not segments:
                return None
            wav = np.concatenate(segments)
            buf = io.BytesIO()
            sf.write(buf, wav, _KOKORO_SAMPLE_RATE, format="WAV", subtype="PCM_16")
            return buf.getvalue()

        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            logger.warning("Kokoro synth failed: %s", e)
            return None

    async def _speak_local(self, text: str, personality: str) -> bool:
        """Speak via offline neural TTS (no network, no clone WAV)."""
        if not await self._ensure_local_tts():
            return False
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        out = Path(tmp)
        try:
            audio = await self._local_tts.synthesize(
                text=text,
                personality=personality,
                output_path=out,
            )
            if not audio and not out.is_file():
                return False
            await self._play_audio_file(str(out))
            return True
        except Exception as e:
            logger.warning("Local TTS speak failed: %s", e)
            return False
        finally:
            try:
                out.unlink(missing_ok=True)
            except OSError:
                pass

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
        elif not self._edge_available and self._local_tts_available:
            # Offline neural default when Edge is unavailable.
            engine = "local-neural"
        stt = None
        if self._mic_available:
            if self._whisper_available:
                stt = f"whisper:{self.whisper_model_name}"
            else:
                stt = "google"
        if cloning:
            note = f"Cloning from {self.clone_wav}"
        elif self._edge_available:
            note = "Neural Edge TTS active"
        elif self._local_tts_available:
            note = "Local neural TTS active (offline)"
        else:
            note = (
                "Robotic pyttsx3 — install edge-tts for online neural voices, "
                "or coqui-tts (python scripts/setup_voice_clone.py) for an "
                "offline neural voice. For cloning: 'voice clone sample.wav'"
            )
        return {
            "tts_available": self._tts_available,
            "tts_engine": engine if self._tts_available else None,
            "edge_available": self._edge_available,
            "pyttsx3_available": self._pyttsx3_available,
            "coqui_available": self._coqui_available,
            "local_tts_available": self._local_tts_available,
            "kokoro_available": self._kokoro_available,
            "voice_id": self.voice_id or _EDGE_VOICES.get("friendly"),
            "voices": voice_catalog(),
            "kokoro_voices": kokoro_voice_catalog(),
            "kokoro_voice": _KOKORO_DEFAULT_VOICE,
            "rate_bias": self.rate_bias,
            "pitch_bias": self.pitch_bias,
            "clone_wav": self.clone_wav,
            "cloning": cloning,
            "stt_available": self._stt_available,
            "stt_engine": stt,
            "whisper_available": self._whisper_available,
            "mic_available": self._mic_available,
            "speak_replies": self.speak_replies,
            "initialized": self.initialized,
            "note": note,
        }

    def apply_voice_style(
        self,
        *,
        voice_id: Optional[str] = None,
        rate_bias: Optional[int] = None,
        pitch_bias: Optional[int] = None,
    ) -> None:
        """Update Edge voice + tempo/pitch biases from Settings."""
        if voice_id is not None:
            vid = (voice_id or "").strip()
            if not vid or vid.lower() in ("auto", "default", "tone"):
                self.voice_id = None
            else:
                self.voice_id = vid
        if rate_bias is not None:
            self.rate_bias = max(-40, min(40, int(rate_bias)))
        if pitch_bias is not None:
            self.pitch_bias = max(-20, min(20, int(pitch_bias)))

    async def speak(self, text: str, personality: str = "friendly") -> bool:
        """Speak text aloud using best available TTS."""
        if not text or not text.strip():
            return False
        if not self._tts_available and not self._coqui_available:
            return False
        if not self.initialized:
            await self.initialize()

        spoken = spoken_excerpt(text, max_chars=280)
        if not spoken:
            return False

        if self.clone_wav and self._coqui_available:
            ok = await self._speak_clone(spoken)
            if ok:
                return True
            logger.warning("Clone speak failed — falling back")

        if self._edge_available:
            ok = await self._speak_edge(spoken, personality)
            if ok:
                return True
            logger.warning("Edge TTS failed — trying local neural fallback")

        if self._local_tts_available:
            ok = await self._speak_local(spoken, personality)
            if ok:
                return True
            logger.warning("Local neural TTS failed — trying pyttsx3 fallback")

        if self._pyttsx3_available:
            return await self._speak_pyttsx3(spoken, personality)

        return False

    async def synthesize(
        self,
        text: str,
        personality: str = "friendly",
        *,
        voice_id: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        rate_bias: Optional[int] = None,
        pitch_bias: Optional[int] = None,
        force_edge: bool = False,
        engine: Optional[str] = None,
        max_chars: int = 420,
    ) -> Optional[tuple[bytes, str]]:
        """Render TTS to bytes without playing (for PWA / API).

        Returns (audio_bytes, mime_type) or None.

        ``engine`` selects the preferred path:
          "natural"   -> Kokoro-82M (offline, natural) then fall back
          "fast"      -> Edge neural (online) then fall back
          "authentic" -> XTTS clone (needs a reference WAV) then fall back
        When ``engine`` is None the legacy behavior applies (clone if
        configured and not ``force_edge``, else Edge, else local neural).
        ``voice_id`` is interpreted as a Kokoro voice for the natural engine
        and as an Edge voice otherwise.
        """
        if not text or not text.strip():
            return None
        if not self.initialized:
            await self.initialize(tts_only=True)

        spoken = speech_for_tts(text, max_chars=max_chars)
        if not spoken:
            return None

        mode = (engine or "").strip().lower()
        if not mode and force_edge:
            mode = "fast"

        storyteller = mode == "storyteller"
        if storyteller:
            # Prefer parent's own XTTS clone, then Edge with storyteller biases.
            mode = "authentic"
            if rate_bias is None:
                rate_bias = STORYTELLER_RATE_BIAS
            if pitch_bias is None:
                pitch_bias = STORYTELLER_PITCH_BIAS

        # Natural (Kokoro) — natural + offline. Preferred mobile default.
        if mode == "natural" and self._kokoro_available:
            data = await self._synth_kokoro_bytes(spoken, voice_id=voice_id)
            if data:
                return data, "audio/wav"

        # Authentic (XTTS clone) — explicit request, storyteller, or legacy default.
        want_clone = mode == "authentic" or (mode == "" and not force_edge)
        if want_clone and self.clone_wav and self._coqui_available:
            data = await self._synth_clone_bytes(spoken)
            if data:
                if storyteller:
                    data = storyteller_shift_wav(data)
                return data, "audio/wav"

        # Fast (Edge neural) — explicit fast/legacy edge path, or fallback.
        edge_voice = voice_id if mode != "natural" else None
        if self._edge_available:
            data = await self._synth_edge_bytes(
                spoken,
                personality,
                voice_id=edge_voice,
                rate=rate,
                pitch=pitch,
                rate_bias=rate_bias,
                pitch_bias=pitch_bias,
            )
            if data:
                return data, "audio/mpeg"

        # Offline neural fallback — Kokoro first (natural), then local Coqui.
        if self._kokoro_available:
            data = await self._synth_kokoro_bytes(spoken, voice_id=voice_id)
            if data:
                return data, "audio/wav"
        if self._local_tts_available:
            data = await self._synth_local_bytes(spoken, personality)
            if data:
                return data, "audio/wav"

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

    def _resolve_edge_voice(
        self, personality: str, voice_id: Optional[str] = None
    ) -> str:
        override = voice_id if voice_id is not None else self.voice_id
        if override and str(override).lower() not in ("auto", "default", "tone"):
            return str(override)
        return _EDGE_VOICES.get(personality, _EDGE_VOICES["friendly"])

    async def _synth_edge_bytes(
        self,
        text: str,
        personality: str,
        *,
        voice_id: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        rate_bias: Optional[int] = None,
        pitch_bias: Optional[int] = None,
    ) -> Optional[bytes]:
        import edge_tts

        voice = self._resolve_edge_voice(personality, voice_id)
        rb = self.rate_bias if rate_bias is None else rate_bias
        pb = self.pitch_bias if pitch_bias is None else pitch_bias
        # Always plain text — never SSML. Passing SSML + rate/pitch to edge-tts
        # often makes the engine literally speak xmlns="http://www.w3.org/…"
        plain = prepare_speech_text(text) or (text or "").strip()
        if not plain:
            return None
        if len(plain) > 560:
            plain = spoken_passage(plain, max_chars=520) or plain[:520]
        if "<" in plain or "xmlns" in plain.lower() or "http://" in plain.lower():
            import re

            plain = prepare_speech_text(re.sub(r"<[^>]+>", " ", plain))
            if not plain:
                return None
        emotion = detect_speech_emotion(plain)
        prosody = resolve_prosody(
            personality,
            rate=rate,
            pitch=pitch,
            volume=self.volume_override,
            rate_bias=rb,
            pitch_bias=pb,
            emotion=emotion,
        )

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            communicate = edge_tts.Communicate(
                plain,
                voice,
                rate=prosody["rate"],
                pitch=prosody["pitch"],
                volume=prosody["volume"],
            )
            await communicate.save(path)
            return Path(path).read_bytes()
        except Exception as e:
            logger.warning("Edge TTS synth failed: %s", e)
            try:
                communicate = edge_tts.Communicate(
                    plain,
                    voice,
                    rate="+5%",
                    pitch="+0Hz",
                    volume="+0%",
                )
                await communicate.save(path)
                return Path(path).read_bytes()
            except Exception as e2:
                logger.warning("Edge TTS plain fallback failed: %s", e2)
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

        voice = self._resolve_edge_voice(personality)
        plain = prepare_speech_text(text) or spoken_excerpt(text, max_chars=280)
        if not plain:
            return False
        # Desktop speaker: plain text only (same SSML-vs-prosody trap as synth)
        prosody = resolve_prosody(
            personality,
            volume=self.volume_override,
            rate_bias=self.rate_bias,
            pitch_bias=self.pitch_bias,
            emotion="neutral",
        )

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            communicate = edge_tts.Communicate(
                plain,
                voice,
                rate=prosody["rate"],
                pitch=prosody["pitch"],
                volume=prosody["volume"],
            )
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

    def transcribe_bytes(
        self, raw: bytes, suffix: str = ".webm"
    ) -> Optional[str]:
        """Transcribe an uploaded voice note (webm/wav/mp3/…) via Whisper."""
        if not raw or len(raw) < 500:
            return None
        suf = suffix if suffix.startswith(".") else f".{suffix}"
        if suf.lower() not in (
            ".wav",
            ".mp3",
            ".webm",
            ".ogg",
            ".m4a",
            ".flac",
            ".mp4",
        ):
            suf = ".webm"
        # Enable whisper probes even if constructed with light=True
        if not self._whisper_available:
            self._faster_whisper_available = _probe_faster_whisper()
            self._openai_whisper_available = _probe_openai_whisper()
            self._whisper_available = (
                self._faster_whisper_available or self._openai_whisper_available
            )
        if not self._whisper_available:
            return None
        fd, tmp = tempfile.mkstemp(suffix=suf)
        os.close(fd)
        path = Path(tmp)
        try:
            path.write_bytes(raw)
            return self._transcribe_wav_path(str(path))
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

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
