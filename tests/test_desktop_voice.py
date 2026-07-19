"""
Unit tests for the zero-dependency offline neural TTS tier in desktop_voice.

These tests never hit the network and never download a model: the Coqui
optimizer is stubbed so we can verify the fallback *selection* logic —
local neural activates only when edge-tts is unavailable, edge still wins
when present, and status()/initialize() report the engine honestly.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.voice_pipeline import desktop_voice as dv  # noqa: E402


class _FakeCoqui:
    """Stub CoquiTTSOptimizer — no model load, no network."""

    def __init__(self, model_name=None, use_gpu=False, **_kw):
        self.model_name = model_name
        self.initialized = False

    async def initialize(self):
        self.initialized = True
        return True

    async def synthesize(self, text, personality="friendly", output_path=None, **_kw):
        if output_path is not None:
            Path(output_path).write_bytes(b"RIFFfakeWAVdata")
        return b"RIFFfakeWAVdata"


def _patch_coqui(monkeypatch):
    monkeypatch.setattr(
        "core.engines.coqui_tts_optimizer.CoquiTTSOptimizer", _FakeCoqui
    )


def _offline_service():
    """A service with edge unavailable but local neural available."""
    svc = dv.DesktopVoiceService(light=True)
    svc._edge_available = False
    svc._pyttsx3_available = False
    svc._coqui_available = True
    svc._local_tts_available = True
    svc.initialized = False
    return svc


def test_local_available_tracks_coqui():
    svc = dv.DesktopVoiceService(light=True)
    # In light mode Coqui probing is skipped, so both are False and equal.
    assert svc._local_tts_available == svc._coqui_available


def test_initialize_reports_local_neural_when_edge_absent(monkeypatch):
    _patch_coqui(monkeypatch)
    svc = _offline_service()
    ok = asyncio.run(svc.initialize(tts_only=True))
    assert ok is True
    assert svc.tts_engine == "local-neural"


def test_synthesize_offline_returns_wav(monkeypatch):
    _patch_coqui(monkeypatch)
    svc = _offline_service()
    res = asyncio.run(svc.synthesize("hello offline world", "friendly"))
    assert res is not None
    audio, mime = res
    assert mime == "audio/wav"
    assert len(audio) > 0


def test_edge_wins_when_available(monkeypatch):
    _patch_coqui(monkeypatch)
    svc = dv.DesktopVoiceService(light=True)
    svc._edge_available = True
    svc._local_tts_available = True
    svc._coqui_available = True
    svc.initialized = True

    called = {"local": False}

    async def fake_edge(spoken, personality, **_kw):
        return b"EDGEMP3"

    async def spy_local(text, personality):
        called["local"] = True
        return b"LOCALWAV"

    svc._synth_edge_bytes = fake_edge
    svc._synth_local_bytes = spy_local

    res = asyncio.run(svc.synthesize("hi", "friendly"))
    assert res is not None
    assert res[1] == "audio/mpeg"
    # Local must not be reached when edge succeeds.
    assert called["local"] is False


def test_synthesize_skips_local_when_unavailable(monkeypatch):
    _patch_coqui(monkeypatch)
    svc = dv.DesktopVoiceService(light=True)
    svc._edge_available = False
    svc._local_tts_available = False
    svc._coqui_available = False
    svc.initialized = True
    res = asyncio.run(svc.synthesize("nothing to speak with", "friendly"))
    assert res is None


def test_status_exposes_local_flag_and_note():
    svc = _offline_service()
    st = svc.status()
    assert st["local_tts_available"] is True
    assert st["tts_engine"] == "local-neural"
    assert "offline" in st["note"].lower()


def test_local_synth_bytes_direct(monkeypatch):
    _patch_coqui(monkeypatch)
    svc = _offline_service()
    data = asyncio.run(svc._synth_local_bytes("direct call", "calm"))
    assert data is not None and len(data) > 0
