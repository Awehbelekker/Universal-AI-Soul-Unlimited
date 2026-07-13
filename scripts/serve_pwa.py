#!/usr/bin/env python3
"""
Serve the Universal Soul PWA and proxy Ollama (avoids browser CORS issues).

Usage:
  python scripts/serve_pwa.py
  python scripts/serve_pwa.py --host 0.0.0.0 --port 8765

Then open http://127.0.0.1:8765 on this PC, or http://<LAN-IP>:8765 on your phone.
On the PC, bind Ollama to LAN if needed: set OLLAMA_HOST=0.0.0.0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DEFAULT_OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def normalize_ollama_url(url: str) -> str:
    u = (url or "").strip() or DEFAULT_OLLAMA
    if "://" not in u:
        u = "http://" + u
    u = u.rstrip("/")
    parsed = urlparse(u)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}:{port}"


class PWAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self):
        if self.path.startswith("/proxy/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, X-Ollama-URL",
            )
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/proxy/"):
            return self._proxy("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/proxy/"):
            return self._proxy("POST")
        self.send_error(405)

    def _proxy(self, method: str) -> None:
        target_base = normalize_ollama_url(
            self.headers.get("X-Ollama-URL") or DEFAULT_OLLAMA
        )
        # /proxy/api/tags -> /api/tags
        suffix = self.path[len("/proxy") :]
        if not suffix.startswith("/"):
            suffix = "/" + suffix
        url = target_base + suffix

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else None

        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "User-Agent": "UniversalSoulAI-PWA-Proxy",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Access-Control-Allow-Origin", "*")
                ctype = resp.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as exc:
            payload = json.dumps({"error": str(exc), "url": url}).encode("utf-8")
            self.send_response(502)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Soul AI PWA + Ollama proxy")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not WEB.is_dir():
        print(f"Missing web/ at {WEB}", file=sys.stderr)
        return 1

    httpd = ThreadingHTTPServer((args.host, args.port), PWAHandler)
    print(f"PWA:   http://127.0.0.1:{args.port}/")
    print(f"LAN:   http://<your-pc-ip>:{args.port}/")
    print(f"Proxy: /proxy/* -> Ollama (header X-Ollama-URL or {DEFAULT_OLLAMA})")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
