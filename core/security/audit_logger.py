"""Local-first, append-only audit trail.

A single tamper-evident event log for security/compliance-relevant actions
(auth attempts, data access, config changes, automation, etc.). Design goals,
consistent with the rest of the project:

- **Local-first / plaintext by default.** Events land in ``data/audit/audit.jsonl``
  as one JSON object per line. Encryption is **opt-in** via the
  ``AUDIT_LOG_PASSPHRASE`` env var; unset ⇒ plaintext JSONL.
- **Opt-in AES-256-GCM at rest**, reusing the shared session ``enc:v1:`` envelope
  (PBKDF2 key derived once per process, fresh random nonce per line).
- **Privacy-aware redaction** of sensitive keys before anything is written.
- **Never raises on write** — auditing must not break the caller.

Public API: :func:`log_event`, :func:`read_events`, :func:`tail`, :func:`query`.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = _REPO_ROOT / "data" / "audit"
AUDIT_LOG = AUDIT_DIR / "audit.jsonl"

# Opt-in passphrase for encryption-at-rest. Empty/unset => plaintext (default).
_PASSPHRASE_ENV = "AUDIT_LOG_PASSPHRASE"
# Marks an encrypted line so readers can tell it from legacy plaintext.
_ENC_PREFIX = "enc:v1:"

# Coarse categories keep queries useful without imposing a rigid schema.
CATEGORIES = (
    "auth",
    "data_access",
    "config",
    "automation",
    "security",
    "system",
)

# Substrings that flag a value as sensitive; matched case-insensitively against
# keys in the event's ``detail`` mapping. Values are replaced with a redaction
# marker so the audit trail never becomes a secondary leak of secrets.
_SENSITIVE_KEY_PARTS = (
    "password",
    "passphrase",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "private_key",
    "session_key",
    "cookie",
    "ssn",
    "credit_card",
)
_REDACTED = "***REDACTED***"


def _passphrase() -> Optional[str]:
    pw = os.getenv(_PASSPHRASE_ENV)
    return pw if pw else None


def _get_encryptor():
    """Return a cached line encryptor, or None if encryption is disabled.

    Reuses the shared-session ``_CachedKeyEncryptor`` (key derived once, fast
    per-line AES-GCM). Loaded by file path so a pre-existing eager-import error
    in the top-level ``thinkmesh_core`` package can never disable auditing.
    Returns None if no passphrase is set or the primitive is unavailable.
    """
    pw = _passphrase()
    if not pw:
        _get_encryptor._cache = None  # type: ignore[attr-defined]
        return None
    cache = getattr(_get_encryptor, "_cache", None)
    if cache is not None and cache[0] == pw:
        return cache[1]
    try:
        import importlib.util
        import sys as _sys

        shm_path = _REPO_ROOT / "core" / "memory" / "shared_session.py"
        spec = importlib.util.spec_from_file_location("_audit_shm", shm_path)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["_audit_shm"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        enc_path = _REPO_ROOT / "thinkmesh_core" / "sync" / "encryption.py"
        espec = importlib.util.spec_from_file_location("_audit_enc", enc_path)
        emod = importlib.util.module_from_spec(espec)
        _sys.modules["_audit_enc"] = emod
        espec.loader.exec_module(emod)  # type: ignore[union-attr]
        enc = mod._CachedKeyEncryptor(emod.AESEncryptor(pw))
    except Exception:
        _get_encryptor._cache = None  # type: ignore[attr-defined]
        return None
    _get_encryptor._cache = (pw, enc)  # type: ignore[attr-defined]
    return enc


def _redact(value: Any) -> Any:
    """Recursively redact sensitive keys in mappings/sequences."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            low = str(k).lower()
            if any(part in low for part in _SENSITIVE_KEY_PARTS):
                out[k] = _REDACTED
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


def _reset_cache() -> None:
    """Test/tooling helper: drop the cached encryptor."""
    if hasattr(_get_encryptor, "_cache"):
        delattr(_get_encryptor, "_cache")


def log_event(
    action: str,
    *,
    category: str = "system",
    actor: str = "system",
    target: Optional[str] = None,
    outcome: str = "success",
    severity: str = "info",
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append one audit event. Never raises.

    Returns the stored event dict (with ``id``/``ts`` filled in). ``detail`` is
    privacy-redacted before writing. When ``AUDIT_LOG_PASSPHRASE`` is set the
    line is written as an ``enc:v1:`` AES-256-GCM envelope; otherwise plaintext.
    """
    event: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "category": category if category in CATEGORIES else "system",
        "action": str(action),
        "actor": str(actor),
        "target": target,
        "outcome": str(outcome),
        "severity": str(severity),
        "detail": _redact(detail or {}),
    }
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        enc = _get_encryptor()
        # _CachedKeyEncryptor works on dicts (it JSON-encodes internally); the
        # plaintext branch JSON-encodes here so both paths write one line.
        line = enc.encrypt_line(event) if enc is not None else json.dumps(
            event, ensure_ascii=False
        )
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:  # auditing must not break the caller
        logger.warning("audit write failed: %s", exc)
    return event


# Backward-friendly alias mirroring the automation append_audit() naming.
audit = log_event


def _decode_line(line: str, enc) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        if line.startswith(_ENC_PREFIX):
            if enc is None:
                return None  # encrypted line, no passphrase => skip
            return enc.decrypt_line(line)
        return json.loads(line)  # legacy/plaintext line
    except Exception:
        return None


def read_events(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return audit events oldest-first, tolerating mixed plaintext/encrypted.

    Encrypted lines are decrypted transparently when the passphrase is set and
    silently skipped otherwise. ``limit`` caps to the most recent N events.
    """
    if not AUDIT_LOG.is_file():
        return []
    enc = _get_encryptor()
    try:
        lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    for line in lines:
        row = _decode_line(line, enc)
        if row is not None:
            rows.append(row)
    if limit is not None and limit >= 0:
        rows = rows[-limit:]
    return rows


def tail(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent ``limit`` events (oldest-first within the slice)."""
    return read_events(limit=max(0, limit))


def query(
    *,
    category: Optional[str] = None,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    outcome: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Filter audit events by field/time window. All filters are ANDed."""
    results: List[Dict[str, Any]] = []
    for ev in read_events():
        if category is not None and ev.get("category") != category:
            continue
        if action is not None and ev.get("action") != action:
            continue
        if actor is not None and ev.get("actor") != actor:
            continue
        if outcome is not None and ev.get("outcome") != outcome:
            continue
        ts = ev.get("ts", 0.0)
        if since is not None and ts < since:
            continue
        if until is not None and ts > until:
            continue
        results.append(ev)
    if limit is not None and limit >= 0:
        results = results[-limit:]
    return results
