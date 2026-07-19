"""
Household / family organization (Phase A–C).

Phase A: family context (opt-in)
Phase B: multi-member profiles + privacy walls
Phase C: shared coordination (reminders / tasks)
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
HOUSEHOLD_PATH = ROOT / "data" / "household.json"
PROFILE_PATH = ROOT / "data" / "user_profiles" / "default.json"

ROLES = ("primary", "partner", "child", "parent", "sibling", "other")


def _audit_auth(action: str, member_id: str, outcome: str) -> None:
    """Record a privacy-wall auth event. Never breaks the caller.

    Imported lazily and guarded so a missing/broken security package can never
    stop PIN verification from working. No PIN value is ever passed in.
    """
    try:
        from core.security import log_event

        log_event(
            action,
            category="auth",
            actor=member_id or "unknown",
            target="household",
            outcome=outcome,
            severity="warning" if outcome == "failure" else "info",
        )
    except Exception:
        pass


def _audit_config(action: str, *, target: str = "household",
                  detail: Optional[Dict[str, Any]] = None) -> None:
    """Record a household config-change event. Never breaks the caller.

    Detail is redacted by the audit logger; callers must still avoid passing
    raw secrets (e.g. PINs) — only pass whether a secret was set.
    """
    try:
        from core.security import log_event

        log_event(
            action,
            category="config",
            actor="household",
            target=target,
            outcome="success",
            detail=detail or {},
        )
    except Exception:
        pass


def _empty_household() -> Dict[str, Any]:
    return {
        "enabled": False,
        "name": "Our household",
        "shared_values": [],
        "boundaries": [],
        "important_dates": [],
        "members": [
            {
                "id": "primary",
                "display_name": "Me",
                "role": "primary",
                "pin": "",
                "notes": "",
            }
        ],
        "board": [],
        "reminders": [],
        "invites": [],
        "updated_at": time.time(),
    }


def load() -> Dict[str, Any]:
    if not HOUSEHOLD_PATH.is_file():
        return _empty_household()
    try:
        data = json.loads(HOUSEHOLD_PATH.read_text(encoding="utf-8"))
        base = _empty_household()
        base.update(data if isinstance(data, dict) else {})
        if not isinstance(base.get("members"), list) or not base["members"]:
            base["members"] = _empty_household()["members"]
        return base
    except Exception:
        return _empty_household()


def save(data: Dict[str, Any]) -> Dict[str, Any]:
    HOUSEHOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["updated_at"] = time.time()
    HOUSEHOLD_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Mirror a short family snippet into default profile preferences
    try:
        _mirror_to_profile(data)
    except Exception:
        pass
    return data


def _mirror_to_profile(data: Dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Any] = {}
    if PROFILE_PATH.is_file():
        try:
            existing = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    prefs = dict(existing.get("preferences") or {})
    prefs["family_enabled"] = bool(data.get("enabled"))
    prefs["household_name"] = data.get("name")
    existing["preferences"] = prefs
    existing["family_context"] = {
        "enabled": bool(data.get("enabled")),
        "name": data.get("name"),
        "member_count": len(data.get("members") or []),
    }
    existing["user_id"] = existing.get("user_id") or "default"
    PROFILE_PATH.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def status() -> Dict[str, Any]:
    data = load()
    return {
        "ok": True,
        "enabled": bool(data.get("enabled")),
        "name": data.get("name"),
        "members": [
            {
                "id": m.get("id"),
                "display_name": m.get("display_name"),
                "role": m.get("role"),
                "has_pin": bool(m.get("pin")),
            }
            for m in (data.get("members") or [])
        ],
        "shared_values": data.get("shared_values") or [],
        "boundaries": data.get("boundaries") or [],
        "important_dates": data.get("important_dates") or [],
        "board_items": len(data.get("board") or []),
        "open_reminders": len(
            [r for r in (data.get("reminders") or []) if not r.get("done")]
        ),
    }


def update_context(body: Dict[str, Any]) -> Dict[str, Any]:
    """Phase A — opt-in family context fields."""
    data = load()
    if "enabled" in body:
        data["enabled"] = bool(body.get("enabled"))
    if body.get("name"):
        data["name"] = str(body["name"]).strip()[:80]
    if "shared_values" in body and isinstance(body["shared_values"], list):
        data["shared_values"] = [str(v).strip()[:80] for v in body["shared_values"] if str(v).strip()][:20]
    if "boundaries" in body and isinstance(body["boundaries"], list):
        data["boundaries"] = [str(v).strip()[:120] for v in body["boundaries"] if str(v).strip()][:20]
    if "important_dates" in body and isinstance(body["important_dates"], list):
        data["important_dates"] = body["important_dates"][:30]
    save(data)
    _audit_config("context_update",
                  detail={"fields": sorted(k for k in body.keys())})
    return {"ok": True, **status()}


def upsert_member(body: Dict[str, Any]) -> Dict[str, Any]:
    """Phase B — add/update household member."""
    data = load()
    members = list(data.get("members") or [])
    mid = (body.get("id") or "").strip() or re.sub(
        r"[^a-z0-9_]+", "_", (body.get("display_name") or "member").lower()
    )[:24]
    role = (body.get("role") or "other").strip().lower()
    if role not in ROLES:
        role = "other"
    display = (body.get("display_name") or mid).strip()[:40]
    pin = str(body.get("pin") or "").strip()[:12]
    notes = str(body.get("notes") or "").strip()[:200]
    found = False
    for m in members:
        if m.get("id") == mid:
            m["display_name"] = display
            m["role"] = role
            if "pin" in body:
                m["pin"] = pin
            if "notes" in body:
                m["notes"] = notes
            found = True
            break
    if not found:
        members.append(
            {
                "id": mid,
                "display_name": display,
                "role": role,
                "pin": pin,
                "notes": notes,
            }
        )
    data["members"] = members
    data["enabled"] = True
    save(data)
    _audit_config(
        "member_update" if found else "member_add",
        target=mid,
        detail={"role": role, "pin_set": bool(pin)},
    )
    return {"ok": True, "member_id": mid, **status()}


def remove_member(member_id: str) -> Dict[str, Any]:
    mid = (member_id or "").strip()
    if mid == "primary":
        return {"ok": False, "error": "Cannot remove primary member"}
    data = load()
    data["members"] = [m for m in (data.get("members") or []) if m.get("id") != mid]
    save(data)
    _audit_config("member_remove", target=mid)
    return {"ok": True, **status()}


def verify_member(member_id: str, pin: str = "") -> Dict[str, Any]:
    """Privacy wall gate — empty pin allowed if member has no pin set."""
    data = load()
    for m in data.get("members") or []:
        if m.get("id") == member_id:
            expected = str(m.get("pin") or "")
            if expected and expected != str(pin or ""):
                _audit_auth("pin_verify", member_id, "failure")
                return {"ok": False, "error": "Wrong PIN", "authenticated": False}
            _audit_auth("pin_verify", member_id, "success")
            return {
                "ok": True,
                "authenticated": True,
                "member": {
                    "id": m.get("id"),
                    "display_name": m.get("display_name"),
                    "role": m.get("role"),
                },
            }
    _audit_auth("pin_verify", member_id, "failure")
    return {"ok": False, "error": "Unknown member", "authenticated": False}


def add_board_fact(text: str, *, member_id: str = "primary") -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "text required"}
    data = load()
    item = {
        "id": str(uuid.uuid4())[:8],
        "text": text[:300],
        "by": member_id,
        "ts": time.time(),
    }
    board = list(data.get("board") or [])
    board.append(item)
    data["board"] = board[-50:]
    data["enabled"] = True
    save(data)
    return {"ok": True, "item": item}


def add_reminder(
    text: str,
    *,
    member_id: str = "primary",
    for_member: str = "",
    when: str = "",
) -> Dict[str, Any]:
    """Phase C — shared reminder / coordination item."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "text required"}
    data = load()
    item = {
        "id": str(uuid.uuid4())[:8],
        "text": text[:300],
        "created_by": member_id,
        "for_member": (for_member or "").strip() or "everyone",
        "when": (when or "").strip()[:80],
        "done": False,
        "ts": time.time(),
    }
    reminders = list(data.get("reminders") or [])
    reminders.append(item)
    data["reminders"] = reminders[-100:]
    data["enabled"] = True
    save(data)
    return {"ok": True, "reminder": item}


def complete_reminder(reminder_id: str) -> Dict[str, Any]:
    data = load()
    rid = (reminder_id or "").strip()
    for r in data.get("reminders") or []:
        if r.get("id") == rid:
            r["done"] = True
            r["done_at"] = time.time()
            save(data)
            return {"ok": True, "reminder": r}
    return {"ok": False, "error": "not found"}


def list_reminders(*, include_done: bool = False) -> Dict[str, Any]:
    data = load()
    items = data.get("reminders") or []
    if not include_done:
        items = [r for r in items if not r.get("done")]
    return {"ok": True, "reminders": items}


def prompt_block(member_id: str = "primary") -> str:
    """Inject into system prompt when family is enabled."""
    data = load()
    if not data.get("enabled"):
        return ""
    lines = [
        f"Family / household context (opt-in): {data.get('name') or 'household'}.",
        "Respect privacy walls: do not leak one member's private chat to another.",
    ]
    vals = data.get("shared_values") or []
    if vals:
        lines.append("Shared family values: " + "; ".join(vals[:12]))
    bounds = data.get("boundaries") or []
    if bounds:
        lines.append("Family boundaries: " + "; ".join(bounds[:12]))
    members = data.get("members") or []
    if members:
        desc = ", ".join(
            f"{m.get('display_name')} ({m.get('role')})" for m in members[:12]
        )
        lines.append(f"Members: {desc}")
    active = next((m for m in members if m.get("id") == member_id), None)
    if active:
        lines.append(
            f"Current speaker: {active.get('display_name')} "
            f"(id={active.get('id')}, role={active.get('role')})."
        )
    board = data.get("board") or []
    if board:
        facts = "; ".join(b.get("text", "") for b in board[-8:])
        lines.append(f"Family board: {facts}")
    open_r = [r for r in (data.get("reminders") or []) if not r.get("done")]
    if open_r:
        rem = "; ".join(
            f"{r.get('text')}"
            + (f" @{r.get('when')}" if r.get("when") else "")
            for r in open_r[:6]
        )
        lines.append(f"Open family reminders: {rem}")
    dates = data.get("important_dates") or []
    if dates:
        lines.append("Important dates: " + "; ".join(str(d)[:60] for d in dates[:8]))
    return "\n".join(lines)


def create_invite(
    *,
    role: str = "sibling",
    display_name: str = "",
    created_by: str = "primary",
    base_url: str = "",
    ttl_hours: int = 72,
) -> Dict[str, Any]:
    """
    Create a one-time (or multi-use until expiry) invite for siblings/staff.
    Returns join_url + qr image URL for PWA onboarding.
    """
    import secrets
    import urllib.parse

    data = load()
    role = (role or "other").strip().lower()
    if role not in ROLES or role == "primary":
        role = "sibling" if "sibling" in ROLES else "other"
    # allow sibling/staff aliases
    if role == "staff":
        role = "other"
    token = secrets.token_urlsafe(16)
    invite = {
        "token": token,
        "role": role,
        "display_name_hint": (display_name or "").strip()[:40],
        "created_by": created_by or "primary",
        "created_at": time.time(),
        "expires_at": time.time() + max(1, int(ttl_hours)) * 3600,
        "uses": 0,
        "max_uses": 1,
        "redeemed_by": [],
    }
    invites = [i for i in (data.get("invites") or []) if float(i.get("expires_at") or 0) > time.time()]
    invites.append(invite)
    data["invites"] = invites[-40:]
    data["enabled"] = True
    save(data)

    base = (base_url or "").rstrip("/")
    join_path = f"/?invite={urllib.parse.quote(token)}"
    join_url = f"{base}{join_path}" if base else join_path
    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/?"
        + urllib.parse.urlencode({"size": "240x240", "data": join_url or join_path})
    )
    return {
        "ok": True,
        "token": token,
        "role": role,
        "join_url": join_url,
        "join_path": join_path,
        "qr_url": qr_url,
        "expires_at": invite["expires_at"],
        "household": data.get("name"),
    }


def peek_invite(token: str) -> Dict[str, Any]:
    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "missing invite token"}
    data = load()
    now = time.time()
    for inv in data.get("invites") or []:
        if inv.get("token") != token:
            continue
        if float(inv.get("expires_at") or 0) < now:
            return {"ok": False, "error": "Invite expired", "expired": True}
        if int(inv.get("uses") or 0) >= int(inv.get("max_uses") or 1):
            return {"ok": False, "error": "Invite already used", "used": True}
        return {
            "ok": True,
            "token": token,
            "role": inv.get("role"),
            "display_name_hint": inv.get("display_name_hint"),
            "household": data.get("name"),
            "expires_at": inv.get("expires_at"),
        }
    return {"ok": False, "error": "Unknown invite"}


def redeem_invite(
    token: str,
    *,
    display_name: str,
    pin: str = "",
) -> Dict[str, Any]:
    """Sibling/staff scans QR → claims membership on this household."""
    token = (token or "").strip()
    display_name = (display_name or "").strip()[:40]
    if not token or not display_name:
        return {"ok": False, "error": "token and display_name required"}
    peek = peek_invite(token)
    if not peek.get("ok"):
        return peek

    data = load()
    inv = next(i for i in (data.get("invites") or []) if i.get("token") == token)
    role = inv.get("role") or "other"
    # create member
    result = upsert_member(
        {
            "display_name": display_name,
            "role": role,
            "pin": pin,
            "notes": f"joined via invite {token[:6]}…",
        }
    )
    if not result.get("ok"):
        return result
    mid = result.get("member_id")
    inv["uses"] = int(inv.get("uses") or 0) + 1
    redeemed = list(inv.get("redeemed_by") or [])
    redeemed.append({"member_id": mid, "at": time.time(), "name": display_name})
    inv["redeemed_by"] = redeemed
    # write invites back
    data = load()
    for i, item in enumerate(data.get("invites") or []):
        if item.get("token") == token:
            data["invites"][i] = inv
            break
    save(data)
    return {
        "ok": True,
        "member_id": mid,
        "display_name": display_name,
        "role": role,
        "household": data.get("name"),
        "message": f"Linked as {display_name} on {data.get('name') or 'household'}.",
    }


def list_invites() -> Dict[str, Any]:
    data = load()
    now = time.time()
    active = []
    for inv in data.get("invites") or []:
        if float(inv.get("expires_at") or 0) < now:
            continue
        if int(inv.get("uses") or 0) >= int(inv.get("max_uses") or 1):
            continue
        active.append(
            {
                "token": inv.get("token"),
                "role": inv.get("role"),
                "display_name_hint": inv.get("display_name_hint"),
                "expires_at": inv.get("expires_at"),
            }
        )
    return {"ok": True, "invites": active}
