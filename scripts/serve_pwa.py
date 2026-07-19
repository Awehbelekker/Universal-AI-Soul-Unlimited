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
import base64
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.integrations import google_oauth, wow_tools
from core.memory import shared_session
from core.family import household
from core.offline import light_pack
from core.routing.task_router import TaskMode, classify_request

WEB = ROOT / "web"
DEFAULT_OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
google_oauth.load_dotenv()

_think_adapter = None
_think_lock = threading.Lock()


def _get_think_adapter():
    global _think_adapter
    with _think_lock:
        if _think_adapter is not None:
            return _think_adapter
        from core.thinkmesh_engine.adapter import ThinkMeshAdapter

        _think_adapter = ThinkMeshAdapter()
        return _think_adapter


def _thinkmesh_sync(task: str) -> Tuple[str, Dict[str, Any]]:
    async def _run():
        adapter = _get_think_adapter()
        await adapter.initialize()
        result = await adapter.think(task, multipass=True)
        return (result.content or "").strip(), dict(result.meta or {})

    return asyncio.run(_run())


def _ollama_generate(
    ollama_url: str, model: str, prompt: str, temperature: float = 0.7,
    num_predict: int = 420,
) -> Tuple[str, Optional[str]]:
    """Call Ollama /api/generate. Returns (text, error)."""
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": temperature},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{normalize_ollama_url(ollama_url)}/api/generate",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "UniversalSoulAI-PWA-Chat",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("response") or "").strip(), None
    except Exception as exc:
        return "", str(exc)


def chat_with_tools(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    PWA chat: shared memory + family context + tools + optional ThinkMesh deep route.
    """
    message = (body.get("message") or body.get("text") or "").strip()
    if not message:
        return {"ok": False, "error": "message required"}

    model = (body.get("model") or "llama3.2:3b").strip() or "llama3.2:3b"
    ollama_url = body.get("ollama_url") or DEFAULT_OLLAMA
    companion = (body.get("companion_name") or "Universal Soul").strip()[:40]
    tone = (body.get("tone") or "friendly").strip() or "friendly"
    member_id = (body.get("member_id") or "primary").strip() or "primary"
    session_id = (body.get("session_id") or shared_session.DEFAULT_SESSION).strip()
    history = body.get("history") or []
    if not isinstance(history, list):
        history = []

    # Prefer shared PC memory when present
    shared = shared_session.recent_turns(
        session_id, limit=12, member_id=member_id, include_shared=True
    )
    if shared:
        history = [{"role": t.get("role"), "text": t.get("text")} for t in shared]

    tools_used: list[Dict[str, Any]] = []
    tool_context = ""
    route_meta: Dict[str, Any] = {}

    intent = wow_tools.detect_intent(message)
    if intent:
        name, args = intent
        result = wow_tools.run_tool(name, args)
        tools_used.append(result)
        tool_context = result.get("summary") or result.get("error") or ""

    # Family reminder quick intent
    low = message.lower()
    if low.startswith("remind ") or low.startswith("reminder "):
        text = message.split(" ", 1)[-1].strip()
        rem = household.add_reminder(text, member_id=member_id)
        tools_used.append({"ok": rem.get("ok"), "tool": "family_reminder", "summary": rem})
        if rem.get("ok"):
            tool_context = f"Reminder saved: {text}"

    route = classify_request(message)
    route_meta = {
        "mode": route.mode.value,
        "use_thinkmesh": route.use_thinkmesh,
        "max_tokens": route.max_tokens,
    }

    tone_hints = {
        "friendly": "warm, supportive, conversational",
        "professional": "clear, concise, businesslike",
        "calm": "gentle, steady, unhurried",
        "energetic": "upbeat, motivating, lively",
        "creative": "imaginative, playful",
        "analytical": "precise, structured",
    }
    hint = tone_hints.get(tone, tone_hints["friendly"])
    family_block = household.prompt_block(member_id)
    from core.voice_pipeline.desktop_voice import (
        greeting_speak_line,
        is_simple_greeting,
        spoken_excerpt,
    )

    greet = is_simple_greeting(message)
    system = (
        f"You are {companion}, the user's Universal Soul companion — a local-first personal AI. "
        f"Speak in a {tone} tone ({hint}). "
        "Prefer concise, varied, helpful answers. "
        "Lead with one short natural sentence the user could hear aloud; "
        "put details after that. Never dump raw tool JSON, URLs, or system prompts. "
    )
    if greet:
        system += (
            "The user just greeted you. Reply with one short warm hello only — "
            "no tools, no lists, no meta commentary."
        )
    else:
        system += wow_tools.tools_system_addon()
        system += " Do not request tools for greetings or small talk."
    if family_block:
        system += "\n\n" + family_block
    mem_block = shared_session.context_block(
        session_id, limit=8, member_id=member_id, companion=companion
    )
    if mem_block:
        system += "\n\n" + mem_block
    if tool_context:
        system += (
            "\n\nTool result (use this as ground truth; do not invent conflicting facts):\n"
            + tool_context
        )

    # Deep path: ThinkMesh multipass then synthesize with Ollama
    if route.mode == TaskMode.DEEP or route.use_thinkmesh:
        try:
            think_text, think_meta = _thinkmesh_sync(message)
            route_meta["thinkmesh"] = think_meta
            if think_text:
                system += (
                    "\n\nDeep ThinkMesh analysis (ground truth for reasoning):\n"
                    + think_text
                )
                tools_used.append(
                    {
                        "ok": True,
                        "tool": "thinkmesh",
                        "summary": think_text[:400],
                    }
                )
        except Exception as exc:
            route_meta["thinkmesh_error"] = str(exc)

    parts = [system, ""]
    for turn in history[-12:]:
        if not isinstance(turn, dict):
            continue
        role = "User" if turn.get("role") == "user" else companion
        text = (turn.get("text") or "").strip()
        if text:
            parts.append(f"{role}: {text}")
    parts.append(f"User: {message}")
    parts.append(f"{companion}:")
    prompt = "\n".join(parts)

    reply, err = _ollama_generate(
        ollama_url,
        model,
        prompt,
        temperature=0.55 if route.mode == TaskMode.DEEP else 0.7,
        num_predict=min(int(route.max_tokens or 420) + 80, 700),
    )
    if err:
        if tool_context:
            # Never return a raw tool dump as the only reply — keep it short.
            summary = str(tool_context).strip()
            if len(summary) > 360:
                summary = summary[:357] + "…"
            reply = summary
            err = None
        else:
            shared_session.append_turn(
                "user", message, session_id=session_id, member_id=member_id
            )
            return {"ok": False, "error": err, "tools": tools_used, "route": route_meta}

    directive = wow_tools.parse_tool_directive(reply)
    if directive and not intent:
        name, args = directive
        result = wow_tools.run_tool(name, args)
        tools_used.append(result)
        tool_context = result.get("summary") or result.get("error") or ""
        follow = (
            system
            + "\n\nTool result (ground truth):\n"
            + tool_context
            + "\n\nNow answer the user in character in 2–5 short sentences. "
            "Start with one spoken-friendly sentence. Do NOT output another TOOL: line.\n\n"
            + f"User: {message}\n{companion}:"
        )
        reply2, err2 = _ollama_generate(ollama_url, model, follow, temperature=0.65)
        if not err2 and reply2:
            reply = wow_tools.strip_tool_directive(reply2)
        else:
            # Fallback: short paraphrase of tool result, not the full dump
            brief = str(tool_context or "").strip()
            if len(brief) > 280:
                brief = brief[:277] + "…"
            reply = brief or wow_tools.strip_tool_directive(reply)
    else:
        reply = wow_tools.strip_tool_directive(reply) or reply

    speak_line = spoken_passage(reply, max_chars=520)
    if greet and not speak_line:
        speak_line = greeting_speak_line(companion)
    elif not speak_line:
        # Prefer silence over speaking tool/prompt garbage
        speak_line = ""

    shared_session.append_turn(
        "user", message, session_id=session_id, member_id=member_id
    )
    shared_session.append_turn(
        "assistant",
        reply,
        session_id=session_id,
        member_id=member_id,
        meta={"privacy": "shared"} if member_id == "primary" else {},
    )

    return {
        "ok": True,
        "reply": reply,
        "speak": speak_line,
        "tools": tools_used,
        "route": route_meta,
        "member_id": member_id,
        "session_id": session_id,
        "search_provider": wow_tools.catalog().get("search_provider"),
        "memory": shared_session.status(session_id),
    }


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
        "google_linked": bool(prefs.get("google_linked")),
        "google_email": prefs.get("google_email"),
        "google_name": prefs.get("google_name"),
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
    if "clone_wav" in body:
        cw = body.get("clone_wav")
        if cw:
            prefs["clone_wav"] = str(cw)
        else:
            prefs.pop("clone_wav", None)
    existing["user_id"] = existing.get("user_id") or "default"
    existing["preferences"] = prefs
    existing["personality_mode"] = tone
    if "values_profile" not in existing:
        existing["values_profile"] = None
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return companion_profile_get()


def _persist_clone_wav(path: Optional[str]) -> None:
    companion_profile_save({"clone_wav": path or ""})


def reset_voice_service() -> None:
    global _voice_service
    with _voice_init_lock:
        _voice_service = None


def voice_clone_save_bytes(
    raw: bytes, filename: str = "clone_ref.wav"
) -> Dict[str, Any]:
    """Save uploaded audio as clone reference and wire it into the voice service."""
    if not raw or len(raw) < 2000:
        return {
            "ok": False,
            "error": "Audio too short — use 6–15 seconds of clear speech.",
        }
    if len(raw) > 8_000_000:
        return {"ok": False, "error": "File too large (max ~8MB)."}

    suffix = Path(filename or "clone_ref.wav").suffix.lower() or ".wav"
    if suffix not in (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm"):
        suffix = ".wav"
    out_dir = ROOT / "data" / "voice_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"clone_ref{suffix}"
    out_path.write_bytes(raw)

    reset_voice_service()
    _persist_clone_wav(str(out_path))

    # Probe Coqui without forcing full init failure if missing
    from core.voice_pipeline.desktop_voice import _probe_coqui

    coqui = _probe_coqui()
    svc = get_voice_service()
    msg = svc.set_clone_wav(str(out_path))
    return {
        "ok": True,
        "path": str(out_path),
        "coqui_available": coqui,
        "cloning": bool(coqui),
        "message": msg,
        "tip": (
            None
            if coqui
            else "Sample saved. Install Coqui with: python scripts/setup_voice_clone.py — until then Edge neural is used."
        ),
    }


def voice_clone_clear() -> Dict[str, Any]:
    reset_voice_service()
    _persist_clone_wav("")
    svc = get_voice_service()
    svc.clear_clone()
    return {"ok": True, "cloning": False, "message": "Clone cleared — using Edge neural."}


def voice_clone_demo_sync() -> Dict[str, Any]:
    async def _run():
        reset_voice_service()
        svc = get_voice_service()
        await svc.initialize(tts_only=True)
        # Temporarily allow edge path
        msg = await svc.make_edge_demo_sample()
        if svc.clone_wav:
            _persist_clone_wav(svc.clone_wav)
        return {
            "ok": "Clone voice set" in msg or "Reference saved" in msg or bool(svc.clone_wav),
            "message": msg,
            "path": svc.clone_wav,
            "coqui_available": bool(svc._coqui_available),
            "cloning": bool(svc.clone_wav) and bool(svc._coqui_available),
        }

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


_stt_service = None
_stt_init_lock = threading.Lock()


def get_stt_service():
    """Whisper-capable service for phone voice notes (separate from light TTS)."""
    global _stt_service
    with _stt_init_lock:
        if _stt_service is not None:
            return _stt_service
        from core.voice_pipeline.desktop_voice import DesktopVoiceService

        svc = DesktopVoiceService(whisper_model="tiny", light=False)
        svc._mic_available = False
        svc._stt_available = False
        _stt_service = svc
        return _stt_service


def transcribe_sync(raw: bytes, filename: str = "note.webm") -> Dict[str, Any]:
    if not raw or len(raw) < 800:
        return {"ok": False, "error": "Voice note too short — speak a bit longer."}
    if len(raw) > 12_000_000:
        return {"ok": False, "error": "Voice note too large (max ~12MB)."}
    suf = Path(filename or "note.webm").suffix.lower() or ".webm"
    try:
        svc = get_stt_service()
        text = svc.transcribe_bytes(raw, suffix=suf)
        if text is None:
            return {
                "ok": False,
                "error": "Speech-to-text unavailable (install faster-whisper on the PC).",
                "whisper": bool(getattr(svc, "_whisper_available", False)),
            }
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "Could not understand — try again clearly."}
        return {
            "ok": True,
            "text": text,
            "engine": getattr(svc, "stt_engine", None) or "whisper",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


_tts_cache: Dict[str, Tuple[bytes, str]] = {}
_tts_cache_lock = threading.Lock()
_TTS_CACHE_MAX = 24


def _tts_cache_key(
    text: str,
    personality: str,
    voice_id: Optional[str],
    rate_bias: Optional[int],
    pitch_bias: Optional[int],
    force_edge: bool,
) -> str:
    return "|".join(
        [
            text.strip().lower(),
            personality or "",
            str(voice_id or "auto"),
            str(rate_bias if rate_bias is not None else 0),
            str(pitch_bias if pitch_bias is not None else 0),
            "1" if force_edge else "0",
        ]
    )


def synthesize_sync(
    text: str,
    personality: str = "friendly",
    *,
    voice_id: Optional[str] = None,
    rate_bias: Optional[int] = None,
    pitch_bias: Optional[int] = None,
    force_edge: bool = False,
    max_chars: int = 420,
) -> Tuple[Optional[bytes], Optional[str], Dict[str, Any]]:
    """Run DesktopVoiceService.synthesize (cached for short identical lines)."""
    from core.voice_pipeline.desktop_voice import speech_for_tts

    spoken = speech_for_tts(text, max_chars=min(max_chars, 520))
    if not spoken:
        return None, None, {"engine": None, "error": "nothing speakable"}
    key = _tts_cache_key(
        spoken, personality, voice_id, rate_bias, pitch_bias, force_edge
    )
    with _tts_cache_lock:
        hit = _tts_cache.get(key)
    if hit:
        data, mime = hit
        return data, mime, {
            "engine": "edge",
            "cloning": False,
            "voice_id": voice_id,
            "cached": True,
        }

    async def _run():
        svc = get_voice_service()
        await svc.initialize(tts_only=True)
        # Do not mutate shared service style from request params — pass through synthesize only
        result = await svc.synthesize(
            spoken,
            personality=personality,
            voice_id=voice_id,
            rate_bias=rate_bias if rate_bias is not None else 0,
            pitch_bias=pitch_bias if pitch_bias is not None else 0,
            force_edge=True,  # PWA speak path is always Edge for speed/reliability
            max_chars=max_chars,
        )
        st = svc.status()
        meta = {
            "engine": "edge",
            "cloning": False,
            "clone_wav": st.get("clone_wav"),
            "voice_id": voice_id or st.get("voice_id"),
            "rate_bias": rate_bias,
            "pitch_bias": pitch_bias,
            "preview": True,
            "cached": False,
        }
        if result is None:
            return None, None, meta
        data, mime = result
        return data, mime, meta

    data, mime, meta = asyncio.run(_run())
    if data and mime and len(spoken) <= 520:
        with _tts_cache_lock:
            if len(_tts_cache) >= _TTS_CACHE_MAX:
                _tts_cache.pop(next(iter(_tts_cache)), None)
            _tts_cache[key] = (data, mime)
    return data, mime, meta


def warmup_tts() -> None:
    """Prime Edge TTS so the first real speak is faster."""
    try:
        synthesize_sync(
            "Hey, I'm Soul. Good to hear from you.",
            "friendly",
            voice_id="auto",
            force_edge=True,
            max_chars=120,
        )
    except Exception:
        pass


def voice_status_sync() -> Dict[str, Any]:
    async def _run():
        from core.voice_pipeline.desktop_voice import voice_catalog

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
            "rate_bias": st.get("rate_bias", 0),
            "pitch_bias": st.get("pitch_bias", 0),
            "voices": voice_catalog(),
            "tip": (
                "Breath pauses + emotion cues improve Edge realism. "
                "Upload a 6–15s sample under Voice clone for real timbre (needs Coqui)."
            ),
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

    def _public_origin(self) -> str:
        """Origin the browser used (for OAuth redirect_uri)."""
        host = self.headers.get("Host") or "127.0.0.1:8765"
        # Prefer forwarded proto when behind a reverse proxy; else http (LAN PWA).
        proto = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip()
        if proto not in ("http", "https"):
            proto = "http"
        return f"{proto}://{host}"

    def _redirect(self, location: str, code: int = 302) -> None:
        self.send_response(code)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/proxy/"):
            return self._proxy("GET")
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)
        if route == "/api/voice-status":
            return self._voice_status()
        if route == "/api/profile":
            return self._json(200, companion_profile_get())
        if route == "/api/google/status":
            st = google_oauth.status()
            st["drive"] = google_oauth.drive_status()
            st["consent_help"] = (
                "If Google says verification required: keep app in Testing, "
                "add your Gmail under OAuth consent screen > Test users, "
                "then Sign in again on http://127.0.0.1:8765/"
            )
            return self._json(200, st)
        if route == "/api/google/start":
            return self._google_start()
        if route == "/api/google/callback":
            return self._google_callback(parsed.query)
        if route == "/api/tools":
            return self._json(200, wow_tools.catalog())
        if route == "/api/memory":
            sid = (qs.get("session_id") or [shared_session.DEFAULT_SESSION])[0]
            mid = (qs.get("member_id") or [None])[0]
            turns = shared_session.recent_turns(
                sid, limit=40, member_id=mid or None, include_shared=True
            )
            return self._json(
                200,
                {
                    "ok": True,
                    "session_id": sid,
                    "turns": turns,
                    "status": shared_session.status(sid),
                },
            )
        if route == "/api/family":
            return self._json(200, household.status())
        if route == "/api/family/reminders":
            return self._json(200, household.list_reminders())
        if route == "/api/family/invites":
            return self._json(200, household.list_invites())
        if route == "/api/family/invite":
            token = (qs.get("token") or [""])[0]
            return self._json(200, household.peek_invite(token))
        if route == "/api/offline-pack":
            return self._json(200, light_pack.build_pack())
        if route == "/api/remote-access":
            port = 8765
            try:
                host = self.headers.get("Host") or ""
                if ":" in host:
                    port = int(host.rsplit(":", 1)[-1])
            except Exception:
                pass
            return self._json(200, remote_access_info(port))
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/proxy/"):
            return self._proxy("POST")
        route = self.path.split("?", 1)[0]
        if route == "/api/speak":
            return self._speak()
        if route == "/api/transcribe":
            return self._transcribe()
        if route == "/api/voice/clone":
            return self._voice_clone()
        if route == "/api/voice/clone/clear":
            return self._json(200, voice_clone_clear())
        if route == "/api/voice/clone/demo":
            return self._json(200, voice_clone_demo_sync())
        if route == "/api/profile":
            body, err = self._read_json_body()
            if err or body is None:
                return self._json(400, {"error": err or "invalid JSON"})
            try:
                return self._json(200, companion_profile_save(body))
            except Exception as exc:
                return self._json(500, {"error": str(exc)})
        if route == "/api/google/disconnect":
            google_oauth.clear_tokens()
            return self._json(200, {"ok": True, "connected": False})
        if route == "/api/google/setup":
            return self._google_setup()
        if route == "/api/google/email":
            return self._google_email()
        if route == "/api/google/drive":
            return self._google_drive()
        if route == "/api/tools/run":
            return self._tools_run()
        if route == "/api/chat":
            return self._chat()
        if route == "/api/memory/clear":
            body, _ = self._read_json_body()
            sid = (body or {}).get("session_id") or shared_session.DEFAULT_SESSION
            return self._json(200, shared_session.clear_session(sid))
        if route == "/api/family":
            return self._family_update()
        if route == "/api/family/member":
            return self._family_member()
        if route == "/api/family/auth":
            return self._family_auth()
        if route == "/api/family/board":
            return self._family_board()
        if route == "/api/family/reminder":
            return self._family_reminder()
        if route == "/api/family/invite":
            return self._family_invite_create()
        if route == "/api/family/invite/redeem":
            return self._family_invite_redeem()
        if route == "/api/offline/reply":
            return self._offline_reply()
        if route == "/api/offline/queue":
            return self._offline_queue()
        if route == "/api/offline/drain":
            # Allow empty body — fix Method/body footguns that looked like 405s
            try:
                _ = self._read_json_body()
            except Exception:
                pass
            return self._json(200, light_pack.drain_queue())
        return self._json(
            405,
            {
                "ok": False,
                "error": f"Method not allowed for {route}",
                "hint": "Use the documented GET/POST route for this API",
            },
        )

    def _family_invite_create(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        base = self._public_origin()
        result = household.create_invite(
            role=str(body.get("role") or "sibling"),
            display_name=str(body.get("display_name") or ""),
            created_by=str(body.get("created_by") or "primary"),
            base_url=base,
            ttl_hours=int(body.get("ttl_hours") or 72),
        )
        return self._json(200 if result.get("ok") else 400, result)

    def _family_invite_redeem(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        result = household.redeem_invite(
            str(body.get("token") or ""),
            display_name=str(body.get("display_name") or ""),
            pin=str(body.get("pin") or ""),
        )
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

    def _family_update(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        return self._json(200, household.update_context(body))

    def _family_member(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        if body.get("remove"):
            return self._json(200, household.remove_member(str(body.get("id") or "")))
        return self._json(200, household.upsert_member(body))

    def _family_auth(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        result = household.verify_member(
            str(body.get("member_id") or body.get("id") or "primary"),
            str(body.get("pin") or ""),
        )
        code = 200 if result.get("ok") else 403
        return self._json(code, result)

    def _family_board(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        return self._json(
            200,
            household.add_board_fact(
                str(body.get("text") or ""),
                member_id=str(body.get("member_id") or "primary"),
            ),
        )

    def _family_reminder(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        if body.get("complete"):
            return self._json(
                200, household.complete_reminder(str(body.get("id") or ""))
            )
        return self._json(
            200,
            household.add_reminder(
                str(body.get("text") or ""),
                member_id=str(body.get("member_id") or "primary"),
                for_member=str(body.get("for_member") or ""),
                when=str(body.get("when") or ""),
            ),
        )

    def _offline_reply(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        result = light_pack.light_reply(str(body.get("message") or body.get("text") or ""))
        return self._json(200, result)

    def _offline_queue(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        return self._json(
            200,
            light_pack.enqueue_sync(
                str(body.get("message") or body.get("text") or ""),
                member_id=str(body.get("member_id") or "primary"),
            ),
        )

    def _read_json_body(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8")), None
        except Exception:
            return None, "invalid JSON"

    def _tools_run(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        name = body.get("tool") or body.get("name") or ""
        args = body.get("args") or {}
        if not isinstance(args, dict):
            args = {"q": str(args)}
        result = wow_tools.run_tool(str(name), args)
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

    def _chat(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        header_url = self.headers.get("X-Ollama-URL")
        if header_url and not body.get("ollama_url"):
            body = dict(body)
            body["ollama_url"] = header_url
        try:
            result = chat_with_tools(body)
        except Exception as exc:
            return self._json(500, {"ok": False, "error": str(exc)})
        code = 200 if result.get("ok") else 502
        return self._json(code, result)

    def _google_start(self) -> None:
        # Google rejects LAN IPs (192.168.x.x) as redirect URIs — must use loopback.
        # Tokens live on the PC; phone PWA reuses them after you sign in on the PC.
        port = 8765
        try:
            host = self.headers.get("Host") or ""
            if ":" in host:
                port = int(host.rsplit(":", 1)[-1])
        except Exception:
            pass
        redirect_uri = f"http://127.0.0.1:{port}/api/google/callback"
        req_host = (self.headers.get("Host") or "").split(":")[0].lower()
        on_lan = req_host not in ("127.0.0.1", "localhost", "")

        url, err = google_oauth.build_auth_url(redirect_uri)
        if err or not url:
            body = (
                "<!doctype html><html><head><meta charset='utf-8'/>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                "<title>Google setup needed</title>"
                "<style>body{font-family:system-ui;background:#0c1614;color:#e8f2ef;"
                "max-width:520px;margin:2rem auto;padding:1rem;line-height:1.45}"
                "code{color:#3ecf9a}a{color:#3ecf9a}</style></head><body>"
                "<h1>Google not configured yet</h1>"
                f"<p>{err or 'Missing client credentials'}.</p>"
                "<p>Paste Client ID + Secret in Settings, then Sign in on the <b>PC</b> browser.</p>"
                "<p>In Google Cloud, add ONLY these redirect URIs (LAN IPs are rejected):</p>"
                f"<p><code>http://127.0.0.1:{port}/api/google/callback</code><br/>"
                f"<code>http://localhost:{port}/api/google/callback</code></p>"
                "<p><a href='/'>Back to Soul</a></p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if on_lan:
            # Phone cannot complete OAuth redirect to 127.0.0.1 on the PC.
            # Show instructions + PC link.
            pc_start = f"http://127.0.0.1:{port}/api/google/start"
            body = (
                "<!doctype html><html><head><meta charset='utf-8'/>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                "<title>Sign in on your PC</title>"
                "<style>body{font-family:system-ui;background:#0c1614;color:#e8f2ef;"
                "max-width:520px;margin:2rem auto;padding:1rem;line-height:1.5}"
                "code{color:#3ecf9a}a.btn{display:inline-block;margin-top:1rem;padding:.75rem 1rem;"
                "background:#3ecf9a;color:#06241a;text-decoration:none;border-radius:12px;"
                "font-weight:650}</style></head><body>"
                "<h1>Open Google Sign-in on your PC</h1>"
                "<p>Google does not allow <code>192.168…</code> redirect URLs "
                "(needs a public domain like .com). Soul keeps tokens on the PC anyway.</p>"
                "<p>On this computer, open:</p>"
                f"<p><code>{pc_start}</code></p>"
                "<p>Or from the PC browser go to Soul at "
                f"<code>http://127.0.0.1:{port}/</code> → Settings → Sign in with Google.</p>"
                "<p>After you approve permissions, your phone (same Wi‑Fi) can use Gmail via the PC.</p>"
                f"<p><a class='btn' href='/'>Back to phone UI</a></p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return self._redirect(url)

    def _google_setup(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        result = google_oauth.save_client_credentials(
            str(body.get("client_id") or ""),
            str(body.get("client_secret") or ""),
        )
        # Include LAN redirect hints for this server
        if result.get("ok"):
            lans = _lan_ips()
            port = 8765
            try:
                host = self.headers.get("Host") or ""
                if ":" in host:
                    port = int(host.rsplit(":", 1)[-1])
            except Exception:
                pass
            result["redirect_uris_hint"] = google_oauth.suggested_redirect_uris(
                port, lans
            )
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

    def _google_callback(self, query: str) -> None:
        qs = parse_qs(query)
        err = (qs.get("error") or [None])[0]
        if err:
            return self._redirect(f"/?google=error&detail={urllib.parse.quote(str(err))}")
        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        if not code or not state:
            return self._redirect("/?google=error&detail=missing_code")
        result = google_oauth.exchange_code(code, state)
        if not result.get("ok"):
            detail = urllib.parse.quote(str(result.get("error") or "exchange_failed")[:200])
            return self._redirect(f"/?google=error&detail={detail}")
        return self._redirect("/?google=connected")

    def _google_email(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json(400, {"ok": False, "error": "invalid JSON"})
        action = (body.get("action") or "draft").strip().lower()
        to = body.get("to") or ""
        subject = body.get("subject") or ""
        text = body.get("body") or body.get("text") or ""
        if action == "send":
            result = google_oauth.send_mail(to, subject, text)
        else:
            result = google_oauth.create_draft(to, subject, text)
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

    def _google_drive(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"ok": False, "error": err or "invalid JSON"})
        action = (body.get("action") or "status").strip().lower()
        if action == "list":
            result = google_oauth.drive_list_soul_files(int(body.get("limit") or 10))
        elif action in ("save", "note", "upload"):
            result = google_oauth.drive_save_note(
                str(body.get("title") or "Soul note"),
                str(body.get("body") or body.get("text") or body.get("content") or ""),
            )
        else:
            result = google_oauth.drive_status()
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

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

    def _transcribe(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"error": err or "invalid JSON"})
        b64 = body.get("audio_b64") or body.get("data") or ""
        if not b64:
            return self._json(400, {"error": "audio_b64 required"})
        if isinstance(b64, str) and "," in b64 and b64.strip().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return self._json(400, {"error": "invalid base64 audio"})
        filename = str(body.get("filename") or "chat_voice_note.webm")
        result = transcribe_sync(raw, filename)
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

    def _voice_clone(self) -> None:
        body, err = self._read_json_body()
        if err or body is None:
            return self._json(400, {"error": err or "invalid JSON"})
        b64 = body.get("audio_b64") or body.get("data") or ""
        if not b64:
            return self._json(400, {"error": "audio_b64 required"})
        if isinstance(b64, str) and "," in b64 and b64.strip().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return self._json(400, {"error": "invalid base64 audio"})
        filename = str(body.get("filename") or "clone_ref.wav")
        result = voice_clone_save_bytes(raw, filename)
        code = 200 if result.get("ok") else 400
        return self._json(code, result)

    def _speak(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json(400, {"error": "invalid JSON"})

        text = (body.get("text") or "").strip()
        personality = (body.get("personality") or "friendly").strip() or "friendly"
        voice_id = body.get("voice_id") or body.get("voice")
        if voice_id is not None:
            voice_id = str(voice_id).strip() or None
        rate_bias = body.get("rate_bias")
        pitch_bias = body.get("pitch_bias")
        # Also accept tempo/pitch as -2..+2 style from sliders (-40..40 / -20..20)
        if rate_bias is None and body.get("tempo") is not None:
            try:
                rate_bias = int(float(body["tempo"]))
            except (TypeError, ValueError):
                rate_bias = None
        if pitch_bias is None and body.get("pitch") is not None:
            try:
                # pitch may be "+2Hz" or integer bias
                p = body["pitch"]
                if isinstance(p, str) and p.endswith("Hz"):
                    pitch_bias = int(p.replace("Hz", "").replace("+", "") or "0")
                else:
                    pitch_bias = int(float(p))
            except (TypeError, ValueError):
                pitch_bias = None
        try:
            if rate_bias is not None:
                rate_bias = int(rate_bias)
            if pitch_bias is not None:
                pitch_bias = int(pitch_bias)
        except (TypeError, ValueError):
            return self._json(400, {"error": "rate_bias/pitch_bias must be integers"})

        if not text:
            return self._json(400, {"error": "text required"})

        force_edge = bool(
            body.get("force_edge")
            or body.get("preview")
            or str(body.get("engine") or "").lower() == "edge"
        )
        preview = bool(body.get("preview"))
        max_chars = 180 if preview else 520
        if body.get("max_chars") is not None:
            try:
                max_chars = max(60, min(900, int(body["max_chars"])))
            except (TypeError, ValueError):
                pass

        try:
            audio, mime, meta = synthesize_sync(
                text,
                personality,
                voice_id=voice_id,
                rate_bias=rate_bias,
                pitch_bias=pitch_bias,
                force_edge=force_edge,
                max_chars=max_chars,
            )
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


def _is_tailscale_ip(ip: str) -> bool:
    """Tailscale uses CGNAT 100.64.0.0/10."""
    try:
        parts = [int(p) for p in ip.split(".")]
        if len(parts) != 4:
            return False
        return parts[0] == 100 and 64 <= parts[1] <= 127
    except Exception:
        return False


def _tailscale_ips() -> list[str]:
    ips: list[str] = []
    # Prefer CLI when installed
    try:
        import subprocess

        out = subprocess.check_output(
            ["tailscale", "ip", "-4"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
        for line in out.splitlines():
            ip = line.strip()
            if ip and _is_tailscale_ip(ip) and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    # Fallback: any local 100.x address
    for ip in _lan_ips():
        if _is_tailscale_ip(ip) and ip not in ips:
            ips.append(ip)
    return ips


def remote_access_info(port: int = 8765) -> Dict[str, Any]:
    lan = [ip for ip in _lan_ips() if not _is_tailscale_ip(ip)]
    ts = _tailscale_ips()
    return {
        "ok": True,
        "port": port,
        "lan_ips": lan,
        "tailscale_ips": ts,
        "lan_urls": [f"http://{ip}:{port}/" for ip in lan],
        "tailscale_urls": [f"http://{ip}:{port}/" for ip in ts],
        "local_url": f"http://127.0.0.1:{port}/",
        "tailscale_installed": bool(ts)
        or _tailscale_cli_present(),
        "howto": (
            "Install Tailscale on PC + phone (same account). Keep serve_pwa "
            "running with --host 0.0.0.0. On mobile data open a Tailscale URL below."
        ),
        "docs": "https://tailscale.com/download",
    }


def _tailscale_cli_present() -> bool:
    try:
        import shutil

        return shutil.which("tailscale") is not None
    except Exception:
        return False


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
    lans = [ip for ip in _lan_ips() if not _is_tailscale_ip(ip)]
    if lans:
        for ip in lans:
            print(f"Phone (Wi-Fi): http://{ip}:{args.port}/")
    else:
        print(f"LAN:   http://<your-pc-ip>:{args.port}/")
    ts = _tailscale_ips()
    if ts:
        for ip in ts:
            print(f"Phone (Tailscale / off-WiFi): http://{ip}:{args.port}/")
    else:
        print("Remote: install Tailscale on PC+phone for access off home Wi-Fi")
    print(f"Proxy: /proxy/* -> Ollama (header X-Ollama-URL or {DEFAULT_OLLAMA})")
    print("Voice: POST /api/speak  GET /api/voice-status (Edge / XTTS on this PC)")
    cat = wow_tools.catalog()
    print(
        f"Tools: GET /api/tools · POST /api/chat · search={cat.get('search_provider')} "
        f"({len(cat.get('tools') or [])} tools)"
    )
    gstat = google_oauth.status()
    if gstat.get("configured"):
        who = gstat.get("email") or "(not connected)"
        print(f"Google: configured · {who} · Connect in PWA Settings")
    else:
        print("Google: not configured — copy .env.example → .env (CLIENT_ID/SECRET)")
    for uri in google_oauth.suggested_redirect_uris(args.port):
        print(f"  OAuth redirect URI to allow: {uri}")
    print("  (Do NOT add 192.168.x.x — Google rejects private LAN IPs)")
    print("  Sign in with Google on the PC browser (127.0.0.1); phone reuses tokens.")
    print("Ctrl+C to stop.")
    threading.Thread(target=warmup_tts, name="tts-warmup", daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
