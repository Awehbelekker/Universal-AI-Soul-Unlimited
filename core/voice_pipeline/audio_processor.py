"""
Audio Processing (local-first)
==============================

Local noise-suppression for microphone input and output enhancement for
synthesized speech. Uses numpy (spectral subtraction + auto-gain) with an
optional scipy path for higher-quality filtering, and degrades gracefully when
neither is available.

No cloud dependency — consistent with the project's local-first voice stack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def _probe_numpy() -> bool:
    try:
        __import__("numpy")
        return True
    except Exception:
        return False


@dataclass
class AudioProcessorConfig:
    """Audio processing configuration (local-first, opt-in stages)."""

    sample_rate: int = 16000
    noise_suppression: bool = True
    auto_gain_control: bool = True
    output_enhancement: bool = True
    suppression_factor: float = 2.0
    target_rms: float = 0.1


class AudioProcessor:
    """Local audio cleanup: input noise suppression + output enhancement."""

    def __init__(self, config: Optional[AudioProcessorConfig] = None) -> None:
        self.config = config or AudioProcessorConfig()
        self._has_numpy = _probe_numpy()
        self._noise_profile: Any = None
        self._gain_history: List[float] = []

    def process_input(self, audio_bytes: bytes) -> bytes:
        """Clean up captured mic audio before STT (16-bit PCM in/out)."""
        if not self._has_numpy or not audio_bytes:
            return audio_bytes
        try:
            import numpy as np

            audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if self.config.noise_suppression:
                audio = self._suppress_noise(audio)
            if self.config.auto_gain_control:
                audio = self._auto_gain(audio)
            return self._to_pcm16(audio)
        except Exception as e:
            logger.warning(f"Input audio processing failed, passing through: {e}")
            return audio_bytes

    def process_output(self, audio_bytes: bytes) -> bytes:
        """Enhance synthesized speech before playback (16-bit PCM in/out)."""
        if not self._has_numpy or not audio_bytes or not self.config.output_enhancement:
            return audio_bytes
        try:
            import numpy as np

            audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            audio = self._enhance_output(audio)
            return self._to_pcm16(audio)
        except Exception as e:
            logger.warning(f"Output audio processing failed, passing through: {e}")
            return audio_bytes

    def _suppress_noise(self, audio: Any) -> Any:
        """Spectral subtraction with an adaptive noise profile."""
        import numpy as np

        fft = np.fft.rfft(audio)
        magnitude = np.abs(fft)
        phase = np.angle(fft)
        if self._noise_profile is None or self._noise_profile.shape != magnitude.shape:
            # Seed the noise profile from the quietest spectral content.
            self._noise_profile = np.minimum(magnitude, np.median(magnitude))
        alpha = 0.1
        self._noise_profile = (1 - alpha) * self._noise_profile + alpha * magnitude
        enhanced = magnitude - self.config.suppression_factor * self._noise_profile
        enhanced = np.maximum(enhanced, 0.1 * magnitude)
        return np.fft.irfft(enhanced * np.exp(1j * phase), len(audio))

    def _auto_gain(self, audio: Any) -> Any:
        """RMS-based automatic gain control with smoothing."""
        import numpy as np

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms <= 0:
            return audio
        gain = self.config.target_rms / rms
        if self._gain_history:
            gain = 0.9 * self._gain_history[-1] + 0.1 * gain
        gain = float(np.clip(gain, 0.1, 10.0))
        self._gain_history.append(gain)
        if len(self._gain_history) > 100:
            self._gain_history = self._gain_history[-50:]
        return audio * gain

    def _enhance_output(self, audio: Any) -> Any:
        """Soft compression + voice-band EQ boost (scipy optional)."""
        import numpy as np

        threshold, ratio = 0.7, 4.0
        compressed = np.where(
            np.abs(audio) > threshold,
            np.sign(audio) * (threshold + (np.abs(audio) - threshold) / ratio),
            audio,
        )
        try:
            from scipy import signal

            b, a = signal.butter(2, [2000, 4000], "band", fs=self.config.sample_rate)
            enhanced = compressed + signal.filtfilt(b, a, compressed) * 0.2
        except Exception:
            if len(compressed) > 1:
                diff = np.diff(compressed, prepend=compressed[0])
                enhanced = compressed + diff * 0.1
            else:
                enhanced = compressed
        max_val = float(np.max(np.abs(enhanced))) if enhanced.size else 0.0
        if max_val > 0.95:
            enhanced = enhanced * (0.95 / max_val)
        return enhanced

    def _to_pcm16(self, audio: Any) -> bytes:
        import numpy as np

        clipped = np.clip(audio, -1.0, 1.0)
        return (clipped * 32767).astype(np.int16).tobytes()
