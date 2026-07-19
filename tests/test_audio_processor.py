"""
Unit tests for local-first audio processing (noise suppression + enhancement).

Deterministic numpy-only paths, no cloud and no scipy requirement, so these
tests are fast and reproducible on any machine.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add the project root to the Python path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.voice_pipeline.audio_processor import (  # noqa: E402
    AudioProcessor,
    AudioProcessorConfig,
)


def _pcm(signal: np.ndarray) -> bytes:
    clipped = np.clip(signal, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


def _num_samples(pcm: bytes) -> int:
    return len(np.frombuffer(pcm, dtype=np.int16))


def test_input_processing_preserves_length():
    proc = AudioProcessor(AudioProcessorConfig())
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    signal = 0.3 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    out = proc.process_input(_pcm(signal))
    assert _num_samples(out) == sr


def test_auto_gain_boosts_quiet_input():
    proc = AudioProcessor(
        AudioProcessorConfig(noise_suppression=False, auto_gain_control=True)
    )
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    quiet = 0.01 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    out = proc.process_input(_pcm(quiet))
    out_arr = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0
    quiet_rms = float(np.sqrt(np.mean(quiet ** 2)))
    out_rms = float(np.sqrt(np.mean(out_arr ** 2)))
    assert out_rms > quiet_rms


def test_output_enhancement_no_clipping():
    proc = AudioProcessor(AudioProcessorConfig(output_enhancement=True))
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    loud = 0.9 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    out = proc.process_output(_pcm(loud))
    out_arr = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0
    assert np.max(np.abs(out_arr)) <= 1.0


def test_empty_audio_is_safe():
    proc = AudioProcessor(AudioProcessorConfig())
    assert proc.process_input(b"") == b""
    assert proc.process_output(b"") == b""


def test_disabled_stages_passthrough_output():
    proc = AudioProcessor(AudioProcessorConfig(output_enhancement=False))
    sr = 4000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 200 * t).astype(np.float32)
    pcm = _pcm(signal)
    assert proc.process_output(pcm) == pcm


def test_config_defaults_are_local_first():
    cfg = AudioProcessorConfig()
    assert cfg.sample_rate == 16000
    assert cfg.noise_suppression is True
    assert cfg.output_enhancement is True
