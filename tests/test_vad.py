"""
Unit tests for local-first Voice Activity Detection.

Exercises the deterministic energy-based path (numpy only, no torch/Silero and
no network), so these tests are fast and reproducible on any machine.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add the project root to the Python path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.voice_pipeline.vad import (  # noqa: E402
    VADConfig,
    VADResult,
    VoiceActivityDetector,
)


def _pcm(signal: np.ndarray) -> bytes:
    """Convert a float [-1, 1] signal to 16-bit PCM bytes."""
    clipped = np.clip(signal, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


def _energy_detector() -> VoiceActivityDetector:
    # prefer_silero=False forces the deterministic energy path.
    return VoiceActivityDetector(VADConfig(prefer_silero=False))


def test_silence_has_no_speech():
    det = _energy_detector()
    silence = np.zeros(16000, dtype=np.float32)
    result = det.detect(_pcm(silence))
    assert isinstance(result, VADResult)
    assert result.backend == "energy"
    assert result.has_speech is False
    assert result.voice_activity_ratio == 0.0


def test_speech_burst_detected():
    det = _energy_detector()
    sr = 16000
    audio = np.zeros(sr, dtype=np.float32)
    # Insert a loud tone burst in the middle (0.4s of 300Hz).
    t = np.linspace(0, 0.4, int(0.4 * sr), endpoint=False)
    burst = 0.6 * np.sin(2 * np.pi * 300 * t)
    audio[sr // 3 : sr // 3 + burst.size] = burst
    result = det.detect(_pcm(audio))
    assert result.has_speech is True
    assert result.voice_activity_ratio > 0.0
    assert 0.0 < result.speech_duration <= result.total_duration


def test_result_durations_consistent():
    det = _energy_detector()
    sr = 16000
    audio = 0.3 * np.random.RandomState(0).randn(sr).astype(np.float32)
    result = det.detect(_pcm(audio))
    assert result.total_duration == pytest.approx(1.0, abs=0.05)
    assert 0.0 <= result.voice_activity_ratio <= 1.0
    assert result.speech_duration <= result.total_duration


def test_empty_audio_is_safe():
    det = _energy_detector()
    result = det.detect(b"")
    assert result.has_speech is False
    assert result.total_duration == 0.0
    assert result.backend == "energy"


def test_config_defaults_are_local_first():
    cfg = VADConfig()
    assert cfg.sample_rate == 16000
    assert cfg.prefer_silero is True
