"""
Voice Activity Detection (local-first)
======================================

Detects speech in raw PCM audio so the mic can listen hands-free without
streaming silence to STT. Prefers Silero VAD (local torch.hub model) and
always falls back to an energy-based detector that needs only numpy.

No cloud dependency — consistent with the project's local-first voice stack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _probe_numpy() -> bool:
    try:
        __import__("numpy")
        return True
    except Exception:
        return False


@dataclass
class VADConfig:
    """Voice activity detection configuration."""

    sample_rate: int = 16000
    threshold: float = 0.5
    min_speech_duration: float = 0.1
    min_silence_duration: float = 0.1
    prefer_silero: bool = True


@dataclass
class VADResult:
    """Outcome of a voice-activity check over an audio buffer."""

    has_speech: bool
    voice_activity_ratio: float
    total_duration: float
    speech_duration: float
    backend: str
    speech_segments: List[Dict[str, float]] = field(default_factory=list)


class VoiceActivityDetector:
    """Local speech detector: Silero when available, else energy-based."""

    def __init__(self, config: Optional[VADConfig] = None) -> None:
        self.config = config or VADConfig()
        self._has_numpy = _probe_numpy()
        self._model = None
        self._get_speech_timestamps = None
        self._backend: Optional[str] = None

    def _load_silero(self) -> bool:
        if self._model is not None:
            return True
        if not self.config.prefer_silero:
            return False
        try:
            import torch

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
            self._model = model
            self._get_speech_timestamps = utils[0]
            self._backend = "silero"
            logger.info("Silero VAD ready")
            return True
        except Exception as e:
            logger.warning("Silero VAD unavailable, using energy VAD: %s", e)
            return False

    def detect(self, audio_bytes: bytes) -> VADResult:
        """Detect voice activity in 16-bit PCM mono audio."""
        if not self._has_numpy:
            # Cannot analyse without numpy — assume speech so STT still runs.
            return VADResult(
                has_speech=True,
                voice_activity_ratio=1.0,
                total_duration=0.0,
                speech_duration=0.0,
                backend="none",
            )

        import numpy as np

        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio /= 32768.0

        if self._load_silero():
            try:
                import torch

                tensor = torch.from_numpy(audio)
                stamps = self._get_speech_timestamps(
                    tensor,
                    self._model,
                    sampling_rate=self.config.sample_rate,
                    threshold=self.config.threshold,
                    min_speech_duration_ms=int(self.config.min_speech_duration * 1000),
                    min_silence_duration_ms=int(self.config.min_silence_duration * 1000),
                )
                total = len(audio) / self.config.sample_rate
                speech = sum(
                    (s["end"] - s["start"]) / self.config.sample_rate for s in stamps
                )
                segments = [
                    {
                        "start": s["start"] / self.config.sample_rate,
                        "end": s["end"] / self.config.sample_rate,
                    }
                    for s in stamps
                ]
                return VADResult(
                    has_speech=bool(stamps),
                    voice_activity_ratio=(speech / total) if total > 0 else 0.0,
                    total_duration=total,
                    speech_duration=speech,
                    backend="silero",
                    speech_segments=segments,
                )
            except Exception as e:
                logger.warning("Silero detect failed, using energy VAD: %s", e)

        return self._energy_detect(audio)

    def _energy_detect(self, audio: Any) -> VADResult:
        """Adaptive RMS-energy VAD (numpy only)."""
        import numpy as np

        sr = self.config.sample_rate
        frame = int(0.025 * sr)
        hop = int(0.010 * sr)
        total = len(audio) / sr if sr else 0.0

        rms: List[float] = []
        for i in range(0, max(0, len(audio) - frame), hop):
            window = audio[i : i + frame]
            rms.append(float(np.sqrt(np.mean(window**2))))

        if not rms:
            return VADResult(False, 0.0, total, 0.0, "energy")

        arr = np.asarray(rms)
        peak = float(arr.max())
        # Below this absolute RMS the buffer is effectively silence.
        if peak < 1e-3:
            return VADResult(False, 0.0, total, 0.0, "energy")
        # Frames above a fraction of the peak count as speech. This is robust to
        # buffers that are mostly silence with a short burst (where an adaptive
        # mean+std threshold would sit above the burst and miss it).
        threshold = max(0.4 * peak, float(arr.mean() + arr.std()))
        ratio = float(np.mean(arr > threshold))
        return VADResult(
            has_speech=ratio > 0.1,
            voice_activity_ratio=ratio,
            total_duration=total,
            speech_duration=ratio * total,
            backend="energy",
        )
