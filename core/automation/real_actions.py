"""
Real CoAct actions (allowlisted) with consent + audit.

Safe defaults: only paths under the project data sandbox (or explicitly
allowlisted roots), and only after consent=True. Destructive ops are
restricted to the sandbox directory.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
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
_MAX_READ_BYTES = 64_000

# Paths CoAct may touch without being a general shell.
_ALLOWED_ROOTS = (
    SANDBOX_DIR.resolve(),
    (_REPO_ROOT / "data").resolve(),
)


@dataclass
class ParsedAction:
    action: str
    path: Optional[str] = None
    text: Optional[str] = None
    dest: Optional[str] = None


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


def _resolve_under_sandbox(raw: str) -> Path:
    """Stricter: only under automation_sandbox (for mkdir/delete/write)."""
    ensure_sandbox()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (SANDBOX_DIR / p).resolve()
    else:
        p = p.resolve()
    p.relative_to(SANDBOX_DIR.resolve())
    return p


def parse_action(description: str) -> Optional[ParsedAction]:
    """Parse a natural-language or CLI-style automation request."""
    text = (description or "").strip()
    if not text:
        return None
    low = text.lower()

    if low in ("info", "sandbox", "automate info", "automate sandbox"):
        return ParsedAction("sandbox_info")

    m = re.match(
        r"^(?:automate\s+)?list(?:\s+dir(?:ectory)?)?(?:\s+(.+))?$",
        text,
        re.IGNORECASE,
    )
    if m:
        path_raw = (m.group(1) or ".").strip() or "."
        return ParsedAction("list_dir", path=path_raw)

    m = re.match(
        r"^(?:automate\s+)?(?:read|cat|show)\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return ParsedAction("read_file", path=m.group(1).strip())

    m = re.match(
        r"^(?:automate\s+)?open(?:\s+(?:folder|path|file))?\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return ParsedAction("open_path", path=m.group(1).strip())

    m = re.match(
        r"^(?:automate\s+)?mkdir\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return ParsedAction("mkdir", path=m.group(1).strip())

    m = re.match(
        r"^(?:automate\s+)?(?:delete|rm|remove)\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return ParsedAction("delete_file", path=m.group(1).strip())

    m = re.match(
        r"^(?:automate\s+)?copy\s+(\S+)\s+(\S+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return ParsedAction(
            "copy_file", path=m.group(1).strip(), dest=m.group(2).strip()
        )

    m = re.match(
        r"^(?:automate\s+)?append(?:\s+to)?\s+(\S+)\s+(.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return ParsedAction(
            "append_file", path=m.group(1).strip(), text=m.group(2).strip()
        )

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


def _ok(action: str, detail: Dict[str, Any], started: float) -> Dict[str, Any]:
    return {
        "success": True,
        "real": True,
        "action": action,
        "detail": detail,
        "execution_time": time.time() - started,
        "steps_completed": 1,
        "total_steps": 1,
        "confidence": 1.0,
        "intermediate_results": [detail],
    }


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
        "dest": action.dest,
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
        if action.action == "sandbox_info":
            entries = sorted(p.name for p in SANDBOX_DIR.iterdir())
            detail = {
                "sandbox": str(SANDBOX_DIR),
                "count": len(entries),
                "entries": entries[:50],
                "allowed_roots": [str(r) for r in _ALLOWED_ROOTS],
            }
            result = _ok("sandbox_info", detail, started)

        elif action.action == "list_dir":
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
            result = _ok("list_dir", detail, started)

        elif action.action == "read_file":
            target = _resolve_under_allowlist(action.path or "")
            if not target.is_file():
                raise FileNotFoundError(f"Not a file: {target}")
            raw = target.read_bytes()
            truncated = len(raw) > _MAX_READ_BYTES
            chunk = raw[:_MAX_READ_BYTES]
            try:
                text = chunk.decode("utf-8")
            except UnicodeDecodeError:
                text = chunk.decode("utf-8", errors="replace")
            detail = {
                "path": str(target),
                "bytes": len(raw),
                "truncated": truncated,
                "text": text,
            }
            result = _ok("read_file", detail, started)

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
            result = _ok("open_path", detail, started)

        elif action.action == "write_note":
            body = (action.text or "").strip()
            if not body:
                raise ValueError("Note text is empty")
            name = time.strftime("note_%Y%m%d_%H%M%S.txt")
            target = _resolve_under_sandbox(name)
            target.write_text(body + "\n", encoding="utf-8")
            detail = {"path": str(target), "bytes": target.stat().st_size}
            result = _ok("write_note", detail, started)

        elif action.action == "append_file":
            body = (action.text or "").strip()
            if not body:
                raise ValueError("Append text is empty")
            target = _resolve_under_sandbox(action.path or "")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as f:
                f.write(body + "\n")
            detail = {"path": str(target), "bytes": target.stat().st_size}
            result = _ok("append_file", detail, started)

        elif action.action == "mkdir":
            target = _resolve_under_sandbox(action.path or "")
            target.mkdir(parents=True, exist_ok=True)
            detail = {"path": str(target), "created": True}
            result = _ok("mkdir", detail, started)

        elif action.action == "copy_file":
            src = _resolve_under_allowlist(action.path or "")
            dest = _resolve_under_sandbox(action.dest or "")
            if not src.is_file():
                raise FileNotFoundError(f"Source not a file: {src}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            detail = {"src": str(src), "dest": str(dest), "bytes": dest.stat().st_size}
            result = _ok("copy_file", detail, started)

        elif action.action == "delete_file":
            target = _resolve_under_sandbox(action.path or "")
            if not target.exists():
                raise FileNotFoundError(f"Not found: {target}")
            if target.is_dir():
                # Only empty dirs
                if any(target.iterdir()):
                    raise PermissionError(
                        "Refusing to delete non-empty directory "
                        "(empty dirs only, sandbox only)"
                    )
                target.rmdir()
                detail = {"path": str(target), "deleted": "dir"}
            else:
                target.unlink()
                detail = {"path": str(target), "deleted": "file"}
            result = _ok("delete_file", detail, started)

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
        "  automate info              — sandbox path + contents\n"
        "  automate list [path]       — list files (default: sandbox)\n"
        "  automate read <path>       — read text file (allowlisted)\n"
        "  automate open <path>       — open file/folder in OS\n"
        "  automate note <text>       — write timestamped note in sandbox\n"
        "  automate append <file> <t> — append line to sandbox file\n"
        "  automate mkdir <path>      — create dir in sandbox\n"
        "  automate copy <src> <dst>  — copy into sandbox\n"
        "  automate delete <path>     — delete sandbox file / empty dir\n"
        "  automate audit [n]         — show last N audit log entries\n"
        "  Chat: include 'with consent' plus matching wording\n"
    )
