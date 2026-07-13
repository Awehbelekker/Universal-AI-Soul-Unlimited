#!/usr/bin/env python3
"""Smoke-test PWA static files + Ollama proxy helpers."""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.serve_pwa import (  # noqa: E402
    DEFAULT_OLLAMA,
    PWAHandler,
    normalize_ollama_url,
)
from http.server import ThreadingHTTPServer


def test_normalize() -> None:
    assert normalize_ollama_url("192.168.1.5") == "http://192.168.1.5:11434"
    assert normalize_ollama_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    print("normalize OK")


def test_files() -> None:
    web = ROOT / "web"
    for name in (
        "index.html",
        "app.js",
        "styles.css",
        "manifest.webmanifest",
        "sw.js",
        "icons/icon.svg",
        "icons/icon-192.png",
        "icons/icon-512.png",
    ):
        assert (web / name).is_file(), name
    print("files OK")


def test_proxy_live() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), PWAHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            html = r.read().decode("utf-8", errors="replace")
            assert "Universal Soul" in html

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/proxy/api/tags",
            headers={"X-Ollama-URL": DEFAULT_OLLAMA},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            assert "models" in data
        print("proxy live OK —", DEFAULT_OLLAMA)

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/voice-status", timeout=90
        ) as r:
            vs = json.loads(r.read().decode("utf-8"))
            assert vs.get("ok") is True, vs
            print("voice-status OK —", vs.get("tts_engine"), "clone=", vs.get("cloning"))

        speak_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/speak",
            data=json.dumps(
                {"text": "Hello from Universal Soul.", "personality": "friendly"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(speak_req, timeout=90) as r:
            audio = r.read()
            ctype = r.headers.get("Content-Type", "")
            assert len(audio) > 100, len(audio)
            assert "audio" in ctype, ctype
            print("speak OK —", ctype, "bytes=", len(audio))
    finally:
        httpd.shutdown()


def main() -> int:
    test_normalize()
    test_files()
    test_proxy_live()
    print("smoke_pwa: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
