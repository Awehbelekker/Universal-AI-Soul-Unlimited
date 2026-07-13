"""
Real CoAct actions (allowlisted) with consent + audit.

First real automation slice — not simulated sleep/hash success.
Safe defaults: only paths under the project data sandbox (or explicitly
allowlisted roots), and only after consent=True.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_DIR = _REPO_ROOT / "data" / "automation_sandbox"
AUDIT_LOG = _REPO_ROOT / "data" / "automation_audit.jsonl"

# Paths CoAct may touch without being a general shell.
_ALLOWED_ROOTS = (
    SANDBOX_DIR.resolve(),
    (_REPO_ROOT / "data").resolve(),
)


@dataclass
class ParsedAction:
    action: str  # list_dir | open_path | write_note
    path: Optional[str] = None
    text: Optional[str] = None


def ensure_sandbox() -> Path:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    return SANDBOX_DIR


def _resolve_under_allowlist(raw: str) -> Path:
    """Resolve path; must stay under allowlisted roots."""
    ensure_sandbox()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (SANDBOX_DIR / p).resolve()
    else:
        p = p.resolve()
    for root in _ALLOWED_ROOTS:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise PermissionError(
        f"Path not allowed (must be under data/ or sandbox): {p}"
    )


def parse_action(description: str) -> Optional[ParsedAction]:
    """Parse a natural-language or CLI-style automation request."""
    text = (description or "").strip()
    if not text:
        return None
    low = text.lower()

    m = re.match(
        r"^(?:automate\s+)?list(?:\s+dir(?:ectory)?)?(?:\s+(.+))?$",
        text,
        re.IGNORECASE,
    )
    if m:
        path_raw = (m.group(1) or ".").strip() or "."
        return ParsedAction("list_dir", path=path_raw)

    m = re.match(
        r"^(?:automate\s+)?open(?:\s+(?:folder|path|file))?\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return ParsedAction("open_path", path=m.group(1).strip())

    m = re.match(
        r"^(?:automate\s+)?(?:write\s+)?note(?:\s+|:)\s*(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return ParsedAction("write_note", text=m.group(1).strip())

    if re.search(r"\blist\b.+\b(sandbox|folder|directory|dir)\b", low) or low in (
        "list sandbox",
        "list the sandbox",
    ):
        return ParsedAction("list_dir", path=".")
    if re.search(r"\bopen\b.+\bsandbox\b", low):
        return ParsedAction("open_path", path=str(SANDBOX_DIR))

    return None


def consent_from_text(text: str) -> bool:
    low = (text or "").lower()
    markers = (
        "with consent",
        "i consent",
        "you have consent",
        "approved",
        "go ahead and",
        "please do it",
        "do it now",
    )
    return any(m in low for m in markers)


def append_audit(entry: Dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    entry.setdefault("id", str(uuid.uuid4()))
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_audit(limit: int = 20) -> List[Dict[str, Any]]:
    if not AUDIT_LOG.is_file():
        return []
    lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in lines[-max(1, limit) :]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def execute_real_action(
    action: ParsedAction,
    *,
    consent: bool,
    source: str = "coact",
    description: str = "",
) -> Dict[str, Any]:
    """Run one allowlisted action. Requires consent=True."""
    ensure_sandbox()
    started = time.time()
    payload: Dict[str, Any] = {
        "action": action.action,
        "path": action.path,
        "source": source,
        "description": description[:500],
        "consent": bool(consent),
    }

    if not consent:
        result = {
            "success": False,
            "real": True,
            "action": action.action,
            "error_message": (
                "Consent required. Re-run with consent "
                "(CLI: confirm 'y', or include 'with consent' in the request)."
            ),
            "execution_time": time.time() - started,
        }
        append_audit({**payload, **result})
        return result

    try:
        if action.action == "list_dir":
            target = _resolve_under_allowlist(action.path or ".")
            if not target.exists():
                raise FileNotFoundError(f"Not found: {target}")
            if target.is_file():
                entries = [target.name]
                kind = "file"
            else:
                entries = sorted(p.name for p in target.iterdir())
                kind = "directory"
            detail = {
                "path": str(target),
                "kind": kind,
                "entries": entries,
                "count": len(entries),
            }
            result = {
                "success": True,
                "real": True,
                "action": "list_dir",
                "detail": detail,
                "execution_time": time.time() - started,
                "steps_completed": 1,
                "total_steps": 1,
                "confidence": 1.0,
                "intermediate_results": [detail],
            }

        elif action.action == "open_path":
            target = _resolve_under_allowlist(action.path or ".")
            if not target.exists():
                raise FileNotFoundError(f"Not found: {target}")
            if os.name == "nt":
                os.startfile(str(target))  # noqa: S606 — allowlisted path only
            elif sys_platform_open(target):
                pass
            else:
                raise RuntimeError("No opener available on this OS")
            detail = {"path": str(target), "opened": True}
            result = {
                "success": True,
                "real": True,
                "action": "open_path",
                "detail": detail,
                "execution_time": time.time() - started,
                "steps_completed": 1,
                "total_steps": 1,
                "confidence": 1.0,
                "intermediate_results": [detail],
            }

        elif action.action == "write_note":
            body = (action.text or "").strip()
            if not body:
                raise ValueError("Note text is empty")
            ensure_sandbox()
            name = time.strftime("note_%Y%m%d_%H%M%S.txt")
            target = (SANDBOX_DIR / name).resolve()
            target.write_text(body + "\n", encoding="utf-8")
            detail = {"path": str(target), "bytes": target.stat().st_size}
            result = {
                "success": True,
                "real": True,
                "action": "write_note",
                "detail": detail,
                "execution_time": time.time() - started,
                "steps_completed": 1,
                "total_steps": 1,
                "confidence": 1.0,
                "intermediate_results": [detail],
            }

        else:
            raise ValueError(f"Unknown action: {action.action}")

        append_audit({**payload, "success": True, "detail": result.get("detail")})
        return result

    except Exception as e:
        result = {
            "success": False,
            "real": True,
            "action": action.action,
            "error_message": str(e),
            "execution_time": time.time() - started,
        }
        append_audit({**payload, **result})
        logger.warning("Real CoAct action failed: %s", e)
        return result


def sys_platform_open(path: Path) -> bool:
    import sys

    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
        return True
    if sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(path)], check=False)
        return True
    return False


def format_action_help() -> str:
    sandbox = str(SANDBOX_DIR)
    return (
        "Real CoAct actions (require consent):\n"
        f"  Sandbox: {sandbox}\n"
        "  automate list [path]     — list files (default: sandbox)\n"
        "  automate open <path>     — open file/folder in OS (allowlisted)\n"
        "  automate note <text>     — write a note into the sandbox\n"
        "  automate audit [n]       — show last N audit log entries\n"
        "  Chat: include 'with consent' plus list/open/note wording\n"
    )
