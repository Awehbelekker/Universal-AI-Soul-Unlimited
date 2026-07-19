"""
Offline LIGHT pack — limited companion when phone has no LAN to the PC brain.

PWA cannot run real GGUF on-device. This pack:
1. Is downloaded while online (`/api/offline-pack`)
2. Powers a small rule/template + cached FAQ brain in the browser / local store
3. Queues user messages for sync when back online

Native Android GGUF remains the Ultimate path; this is the honest PWA bridge.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.family import household
from core.memory import shared_session

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "data" / "offline_pack.json"
PROFILE_PATH = ROOT / "data" / "user_profiles" / "default.json"
QUEUE_PATH = ROOT / "data" / "offline_sync_queue.jsonl"


def _profile_slice() -> Dict[str, Any]:
    if not PROFILE_PATH.is_file():
        return {}
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    prefs = data.get("preferences") or {}
    values = data.get("values_profile") or {}
    return {
        "companion_name": prefs.get("companion_name") or "Universal Soul",
        "tone": prefs.get("tone") or data.get("personality_mode") or "friendly",
        "core_values": (values.get("core_values") or [])[:12],
        "boundaries": (values.get("boundaries") or [])[:12],
    }


def build_pack() -> Dict[str, Any]:
    """Snapshot for phone offline mode."""
    hh = household.status()
    mem = shared_session.recent_turns(limit=8)
    profile = _profile_slice()
    faq = [
        {
            "q": "who are you",
            "a": f"I'm {profile.get('companion_name', 'your Soul')} — limited offline mode. "
            "Reconnect to your PC for full brain, tools, and voice.",
        },
        {
            "q": "what can you do offline",
            "a": "I can use cached profile, family context, recent memory snippets, "
            "and queue messages to sync when you're back on the LAN.",
        },
        {
            "q": "family",
            "a": (
                f"Household '{hh.get('name')}' is "
                + ("enabled" if hh.get("enabled") else "not enabled")
                + f" with {len(hh.get('members') or [])} members."
            ),
        },
    ]
    pack = {
        "ok": True,
        "version": 1,
        "built_at": time.time(),
        "mode": "offline_light_pack",
        "note": (
            "Limited offline companion for PWA. Real on-device GGUF LIGHT "
            "requires native Android — see VISION.md."
        ),
        "profile": profile,
        "family": hh if hh.get("enabled") else {"enabled": False},
        "memory_snippets": [
            {"role": t.get("role"), "text": (t.get("text") or "")[:240]} for t in mem
        ],
        "faq": faq,
        "canned": {
            "greeting": f"Hi — I'm {profile.get('companion_name', 'Soul')} in limited offline mode.",
            "no_pc": (
                "I can't reach your PC brain right now. I can still use cached "
                "context; full tools/voice need the LAN."
            ),
        },
    }
    PACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    PACK_PATH.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    return pack


def load_pack() -> Dict[str, Any]:
    if PACK_PATH.is_file():
        try:
            return json.loads(PACK_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return build_pack()


def light_reply(message: str, pack: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tiny deterministic LIGHT brain using the offline pack (no GPU)."""
    pack = pack or load_pack()
    msg = (message or "").strip().lower()
    profile = pack.get("profile") or {}
    name = profile.get("companion_name") or "Soul"

    if not msg:
        return {
            "ok": True,
            "reply": pack.get("canned", {}).get("greeting") or f"Hi — {name}.",
            "engine": "offline_light",
        }

    for item in pack.get("faq") or []:
        q = (item.get("q") or "").lower()
        if q and q in msg:
            return {"ok": True, "reply": item.get("a") or "", "engine": "offline_light"}

    if any(w in msg for w in ("hello", "hi ", "hey", "good morning", "good evening")):
        return {
            "ok": True,
            "reply": pack.get("canned", {}).get("greeting")
            or f"Hi — I'm {name} (offline light).",
            "engine": "offline_light",
        }

    if "remind" in msg or "reminder" in msg:
        return {
            "ok": True,
            "reply": (
                "I'll queue that reminder idea. When you're back on Wi‑Fi with the PC, "
                "open Family reminders to add it properly — or say it again online."
            ),
            "engine": "offline_light",
            "queue_hint": "reminder",
        }

    # Values / family snippets
    vals = profile.get("core_values") or []
    if "value" in msg and vals:
        return {
            "ok": True,
            "reply": "From your cached values: " + "; ".join(vals[:6]),
            "engine": "offline_light",
        }

    fam = pack.get("family") or {}
    if fam.get("enabled") and ("family" in msg or "household" in msg):
        members = fam.get("members") or []
        names = ", ".join(m.get("display_name") or m.get("id") for m in members[:8])
        return {
            "ok": True,
            "reply": f"Cached household '{fam.get('name')}': {names or 'no members listed'}.",
            "engine": "offline_light",
        }

    snippets = pack.get("memory_snippets") or []
    hint = ""
    if snippets:
        last = snippets[-1]
        hint = f" Last shared note: {(last.get('text') or '')[:120]}"

    return {
        "ok": True,
        "reply": (
            f"{pack.get('canned', {}).get('no_pc') or 'Offline light mode.'} "
            f"You said: “{(message or '')[:180]}”. "
            f"I'll keep this short until the PC brain is reachable.{hint}"
        ),
        "engine": "offline_light",
        "degraded": True,
    }


def enqueue_sync(message: str, *, member_id: str = "primary") -> Dict[str, Any]:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "member_id": member_id,
        "text": (message or "").strip()[:2000],
    }
    with QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True, "queued": True}


def drain_queue() -> Dict[str, Any]:
    if not QUEUE_PATH.is_file():
        return {"ok": True, "items": []}
    items: List[Dict[str, Any]] = []
    try:
        text = QUEUE_PATH.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        items = []
    QUEUE_PATH.unlink(missing_ok=True)
    # Persist into shared memory as system-noted offline backlog
    for it in items:
        shared_session.append_turn(
            "user",
            it.get("text") or "",
            member_id=it.get("member_id") or "primary",
            meta={"privacy": "shared", "source": "offline_queue"},
        )
    return {"ok": True, "items": items, "count": len(items)}
