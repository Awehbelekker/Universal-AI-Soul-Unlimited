"""
Unit tests for the opt-in premium cloud voice providers.

These tests never hit the network: they verify the opt-in gating (a provider is
inactive without an API key) and that every call degrades to the caller-supplied
local fallback, preserving the local-first default.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add the project root to the Python path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.voice_pipeline.cloud_providers import (  # noqa: E402
    DeepgramSTTProvider,
    ElevenLabsTTSProvider,
    OmniVoiceSTTProvider,
    OmniVoiceTTSProvider,
    OMNIVOICE_DEFAULT_URL,
)


def test_elevenlabs_inactive_without_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    provider = ElevenLabsTTSProvider({})
    assert provider.available is False


def test_deepgram_inactive_without_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    provider = DeepgramSTTProvider({})
    assert provider.available is False


def test_elevenlabs_reads_env_key(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    provider = ElevenLabsTTSProvider({})
    assert provider.api_key == "test-key"


def test_elevenlabs_falls_back_to_local(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    provider = ElevenLabsTTSProvider({})

    def local_tts(text: str) -> bytes:
        return b"LOCAL_AUDIO"

    result = asyncio.run(provider.synthesize("hello", local_fallback=local_tts))
    assert result == b"LOCAL_AUDIO"


def test_deepgram_falls_back_to_local(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    provider = DeepgramSTTProvider({})

    def local_stt(audio: bytes) -> str:
        return "local transcript"

    result = asyncio.run(provider.transcribe(b"\x00\x00", local_fallback=local_stt))
    assert result == "local transcript"


def test_elevenlabs_fallback_none_returns_empty(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    provider = ElevenLabsTTSProvider({})
    result = asyncio.run(provider.synthesize("hello"))
    assert result == b""


def test_explicit_key_sets_api_key():
    provider = DeepgramSTTProvider({"api_key": "explicit"})
    assert provider.api_key == "explicit"


# --- OmniVoice local premium tier (HTTP to a separate local process) ---------


def test_omnivoice_tts_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("OMNIVOICE_BASE_URL", raising=False)
    provider = OmniVoiceTTSProvider({})
    assert provider.base_url == OMNIVOICE_DEFAULT_URL.rstrip("/")


def test_omnivoice_stt_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("OMNIVOICE_BASE_URL", raising=False)
    provider = OmniVoiceSTTProvider({})
    assert provider.base_url == OMNIVOICE_DEFAULT_URL.rstrip("/")


def test_omnivoice_reads_env_url(monkeypatch):
    monkeypatch.setenv("OMNIVOICE_BASE_URL", "http://127.0.0.1:9999/v1/")
    provider = OmniVoiceTTSProvider({})
    # Trailing slash is normalized away.
    assert provider.base_url == "http://127.0.0.1:9999/v1"


def test_omnivoice_requires_no_api_key():
    # A local provider must be usable without any key configured.
    tts = OmniVoiceTTSProvider({})
    stt = OmniVoiceSTTProvider({})
    assert not hasattr(tts, "api_key")
    assert not hasattr(stt, "api_key")


def test_omnivoice_tts_falls_back_when_server_down(monkeypatch):
    # Point at an unreachable port so the HTTP call fails fast.
    provider = OmniVoiceTTSProvider({"base_url": "http://127.0.0.1:1/v1", "timeout_s": 1})

    def local_tts(text: str) -> bytes:
        return b"LOCAL_AUDIO"

    result = asyncio.run(provider.synthesize("hello", local_fallback=local_tts))
    assert result == b"LOCAL_AUDIO"
    asyncio.run(provider.shutdown())


def test_omnivoice_stt_falls_back_when_server_down(monkeypatch):
    provider = OmniVoiceSTTProvider({"base_url": "http://127.0.0.1:1/v1", "timeout_s": 1})

    def local_stt(audio: bytes) -> str:
        return "local transcript"

    result = asyncio.run(provider.transcribe(b"\x00\x00", local_fallback=local_stt))
    assert result == "local transcript"
    asyncio.run(provider.shutdown())
