#!/usr/bin/env python3
"""
Serve the Universal Soul PWA, proxy Ollama, and synthesize voice on the PC.

Usage:
  python scripts/serve_pwa.py
  python scripts/serve_pwa.py --host 0.0.0.0 --port 8765

Phone opens http://<LAN-IP>:8765 — chat + optional Speak replies (Edge / clone).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WEB = ROOT / "web"
DEFAULT_OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

_voice_service = None
_voice_init_lock = threading.Lock()


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


def _load_clone_from_profile() -> Optional[str]:
    profile = _read_default_profile()
    if not profile:
        return None
    prefs = profile.get("preferences") or {}
    wav = prefs.get("clone_wav")
    if wav and Path(wav).is_file():
        return str(wav)
    return None


def _read_default_profile() -> Optional[Dict[str, Any]]:
    profiles = ROOT / "data" / "user_profiles"
    if not profiles.is_dir():
        return None
    candidates = sorted(profiles.glob("*.json"))
    preferred = [p for p in candidates if p.stem.lower() == "default"] + [
        p for p in candidates if p.stem.lower() != "default"
    ]
    for path in preferred:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def _default_profile_path() -> Path:
    return ROOT / "data" / "user_profiles" / "default.json"


def companion_profile_get() -> Dict[str, Any]:
    data = _read_default_profile() or {}
    prefs = data.get("preferences") or {}
    tone = prefs.get("tone") or data.get("personality_mode") or "friendly"
    return {
        "ok": True,
        "companion_name": prefs.get("companion_name") or "Universal Soul",
        "tone": tone,
        "personality_mode": data.get("personality_mode") or tone,
        "clone_wav": prefs.get("clone_wav"),
        "has_clone": bool(
            prefs.get("clone_wav") and Path(str(prefs.get("clone_wav"))).is_file()
        ),
    }


def companion_profile_save(body: Dict[str, Any]) -> Dict[str, Any]:
    path = _default_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    prefs = dict(existing.get("preferences") or {})
    name = (body.get("companion_name") or prefs.get("companion_name") or "Universal Soul")
    name = str(name).strip()[:40] or "Universal Soul"
    tone = (body.get("tone") or prefs.get("tone") or "friendly").strip().lower()
    allowed = {
        "professional",
        "friendly",
        "energetic",
        "calm",
        "creative",
        "analytical",
    }
    if tone not in allowed:
        tone = "friendly"
    prefs["companion_name"] = name
    prefs["tone"] = tone
    existing["user_id"] = existing.get("user_id") or "default"
    existing["preferences"] = prefs
    existing["personality_mode"] = tone
    if "values_profile" not in existing:
        existing["values_profile"] = None
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return companion_profile_get()


def get_voice_service():
    global _voice_service
    with _voice_init_lock:
        if _voice_service is not None:
            return _voice_service
        from core.voice_pipeline.desktop_voice import DesktopVoiceService

        svc = DesktopVoiceService(light=True)
        clone = os.environ.get("SOUL_CLONE_WAV") or _load_clone_from_profile()
        if clone:
            try:
                # Enable Coqui only when a clone sample is configured
                from core.voice_pipeline.desktop_voice import _probe_coqui

                svc._coqui_available = _probe_coqui()
                svc._tts_available = (
                    svc._edge_available
                    or svc._pyttsx3_available
                    or svc._coqui_available
                )
                svc.set_clone_wav(clone)
            except Exception:
                pass
        _voice_service = svc
        return _voice_service


def synthesize_sync(
    text: str, personality: str = "friendly"
) -> Tuple[Optional[bytes], Optional[str], Dict[str, Any]]:
    """Run DesktopVoiceService.synthesize on a fresh event loop."""

    async def _run():
        svc = get_voice_service()
        await svc.initialize(tts_only=True)
        result = await svc.synthesize(text, personality=personality)
        st = svc.status()
        meta = {
            "engine": "clone" if st.get("cloning") else st.get("tts_engine"),
            "cloning": bool(st.get("cloning")),
            "clone_wav": st.get("clone_wav"),
            "voice_id": st.get("voice_id"),
        }
        if result is None:
            return None, None, meta
        data, mime = result
        return data, mime, meta

    return asyncio.run(_run())


def voice_status_sync() -> Dict[str, Any]:
    async def _run():
        svc = get_voice_service()
        await svc.initialize(tts_only=True)
        st = svc.status()
        return {
            "ok": True,
            "tts_engine": st.get("tts_engine"),
            "cloning": bool(st.get("cloning")),
            "clone_wav": st.get("clone_wav"),
            "edge_available": st.get("edge_available"),
            "coqui_available": st.get("coqui_available"),
            "voice_id": st.get("voice_id"),
        }

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"ok": False, "error": str(e)}


class PWAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Ollama-URL",
        )

    def do_OPTIONS(self):
        if self.path.startswith("/proxy/") or self.path.startswith("/api/"):
            self.send_response(204)
            self._cors()
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/proxy/"):
            return self._proxy("GET")
        route = self.path.split("?", 1)[0]
        if route == "/api/voice-status":
            return self._voice_status()
        if route == "/api/profile":
            return self._json(200, companion_profile_get())
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/proxy/"):
            return self._proxy("POST")
        route = self.path.split("?", 1)[0]
        if route == "/api/speak":
            return self._speak()
        if route == "/api/profile":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                return self._json(400, {"error": "invalid JSON"})
            try:
                return self._json(200, companion_profile_save(body))
            except Exception as exc:
                return self._json(500, {"error": str(exc)})
        self.send_error(405)

    def _json(self, code: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _voice_status(self) -> None:
        self._json(200, voice_status_sync())

    def _speak(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json(400, {"error": "invalid JSON"})

        text = (body.get("text") or "").strip()
        personality = (body.get("personality") or "friendly").strip() or "friendly"
        if not text:
            return self._json(400, {"error": "text required"})

        try:
            audio, mime, meta = synthesize_sync(text, personality)
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

        if not audio or not mime:
            return self._json(
                503,
                {
                    "error": "TTS unavailable (install edge-tts on the PC)",
                    "meta": meta,
                },
            )

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("X-Soul-TTS-Engine", str(meta.get("engine") or ""))
        self.send_header(
            "X-Soul-TTS-Cloning", "1" if meta.get("cloning") else "0"
        )
        self.end_headers()
        self.wfile.write(audio)

    def _proxy(self, method: str) -> None:
        target_base = normalize_ollama_url(
            self.headers.get("X-Ollama-URL") or DEFAULT_OLLAMA
        )
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
                "Content-Type": self.headers.get(
                    "Content-Type", "application/json"
                ),
                "User-Agent": "UniversalSoulAI-PWA-Proxy",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self._cors()
                ctype = resp.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as exc:
            payload = json.dumps({"error": str(exc), "url": url}).encode("utf-8")
            self.send_response(502)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def _lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        import socket

        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and ip not in ips:
            ips.insert(0, ip)
    except Exception:
        pass
    return ips


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
    lans = _lan_ips()
    if lans:
        for ip in lans:
            print(f"Phone: http://{ip}:{args.port}/")
    else:
        print(f"LAN:   http://<your-pc-ip>:{args.port}/")
    print(f"Proxy: /proxy/* -> Ollama (header X-Ollama-URL or {DEFAULT_OLLAMA})")
    print("Voice: POST /api/speak  GET /api/voice-status (Edge / XTTS on this PC)")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
