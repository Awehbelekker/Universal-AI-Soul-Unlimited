#!/usr/bin/env python3
"""Smoke-test Android thin-client Ollama helpers (no Kivy required)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_main import (  # noqa: E402
    OllamaClient,
    load_ollama_settings,
    normalize_ollama_url,
    save_ollama_settings,
)


def test_normalize() -> None:
    assert normalize_ollama_url("192.168.1.10") == "http://192.168.1.10:11434"
    assert normalize_ollama_url("http://192.168.1.10") == "http://192.168.1.10:11434"
    assert (
        normalize_ollama_url("http://192.168.1.10:11434/")
        == "http://192.168.1.10:11434"
    )
    print("normalize OK")


def test_persist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = save_ollama_settings("10.0.0.5", "llama3.2:3b", user_data_dir=tmp)
        assert path.is_file()
        url, model = load_ollama_settings(user_data_dir=tmp)
        # env may override in real env — clear for this check via file content
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["ollama_url"] == "http://10.0.0.5:11434"
        assert data["ollama_model"] == "llama3.2:3b"
        assert url  # loaded something
        assert model
    print("persist OK")


def test_probe_mock() -> None:
    client = OllamaClient("http://127.0.0.1:11434", "llama3.2:3b")
    fake_body = json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()

    class Resp:
        status = 200

        def read(self):
            return fake_body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("urllib.request.urlopen", return_value=Resp()):
        probe = client.probe(retries=1)
    assert probe["ok"] is True
    assert "llama3.2:3b" in probe["models"]
    print("probe OK")


def test_probe_fail() -> None:
    client = OllamaClient("http://127.0.0.1:9", "x")
    with patch(
        "urllib.request.urlopen", side_effect=OSError("connection refused")
    ):
        probe = client.probe(retries=1, timeout=0.5)
    assert probe["ok"] is False
    assert probe.get("hint")
    print("probe_fail OK")


def main() -> int:
    test_normalize()
    test_persist()
    test_probe_mock()
    test_probe_fail()
    print("smoke_android_ollama: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
