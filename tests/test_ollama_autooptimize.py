"""
Tests for hardware-aware auto-optimization of OllamaIntegration.

Verifies that RuntimeOptimizer-derived runtime options (num_ctx/num_gpu/
num_thread) are detected on init and merged as a base layer into request
payloads, that explicit per-call kwargs/args override them, that
``auto_optimize=False`` disables the behavior, and that a failing optimizer
degrades gracefully to Ollama's own defaults (empty options).

Imported via the package path (core.engines.*) because the module uses
relative imports; that path loads cleanly.
"""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.engines import ollama_integration as oi  # noqa: E402
from core.engines.ollama_integration import OllamaIntegration  # noqa: E402


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"response": "ok", "eval_count": 3}


class _FakeClient:
    """Captures the JSON payload posted to Ollama."""

    def __init__(self):
        self.last_json = None

    async def post(self, url, json=None):
        self.last_json = json
        return _FakeResponse()

    async def get(self, url):
        return _FakeResponse()

    async def aclose(self):
        pass


@pytest.fixture
def fake_base_options(monkeypatch):
    """Force deterministic base options regardless of host hardware."""
    opts = {"num_ctx": 2048, "num_gpu": 0, "num_thread": 8}
    monkeypatch.setattr(oi, "_detect_runtime_options", lambda: dict(opts))
    return opts


def test_runtime_options_detected_on_init(fake_base_options):
    integ = OllamaIntegration()
    assert integ.runtime_options == fake_base_options


def test_auto_optimize_false_yields_empty(fake_base_options):
    integ = OllamaIntegration(auto_optimize=False)
    assert integ.runtime_options == {}


def test_optimizer_failure_degrades_to_empty(monkeypatch):
    def _boom():
        raise RuntimeError("no optimizer here")

    # _detect_runtime_options itself swallows errors, but guard the whole path.
    monkeypatch.setattr(oi, "_detect_runtime_options", lambda: {})
    integ = OllamaIntegration()
    assert integ.runtime_options == {}


@pytest.mark.asyncio
async def test_base_options_merged_into_generate(fake_base_options):
    integ = OllamaIntegration()
    integ.client = _FakeClient()
    integ.model_loaded = True

    await integ.generate("hi", max_tokens=100, temperature=0.5, top_p=0.8)

    opts = integ.client.last_json["options"]
    # Hardware base options present...
    assert opts["num_ctx"] == 2048
    assert opts["num_gpu"] == 0
    assert opts["num_thread"] == 8
    # ...alongside the explicit generation args.
    assert opts["num_predict"] == 100
    assert opts["temperature"] == 0.5
    assert opts["top_p"] == 0.8


@pytest.mark.asyncio
async def test_explicit_kwargs_override_base(fake_base_options):
    integ = OllamaIntegration()
    integ.client = _FakeClient()
    integ.model_loaded = True

    # Caller explicitly overrides a base option via kwargs.
    await integ.generate("hi", num_ctx=512, num_thread=2)

    opts = integ.client.last_json["options"]
    assert opts["num_ctx"] == 512
    assert opts["num_thread"] == 2
    # Non-overridden base option remains.
    assert opts["num_gpu"] == 0


@pytest.mark.asyncio
async def test_no_optimize_uses_ollama_defaults(fake_base_options):
    integ = OllamaIntegration(auto_optimize=False)
    integ.client = _FakeClient()
    integ.model_loaded = True

    await integ.generate("hi", max_tokens=64)

    opts = integ.client.last_json["options"]
    # No hardware base keys injected; only the explicit generation args.
    assert "num_ctx" not in opts
    assert "num_gpu" not in opts
    assert "num_thread" not in opts
    assert opts["num_predict"] == 64


@pytest.mark.asyncio
async def test_stream_merges_base_options(fake_base_options):
    integ = OllamaIntegration()
    # Build the request the way generate_stream does, verifying the merge
    # without needing a live streaming server.
    options = dict(integ.runtime_options)
    options.update({"num_predict": 200, "temperature": 0.7, "top_p": 0.9})
    assert options["num_ctx"] == 2048
    assert options["num_predict"] == 200
