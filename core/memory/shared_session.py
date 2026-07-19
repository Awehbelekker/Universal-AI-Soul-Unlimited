"""
Shared session memory for desktop + PWA (PC-local store).

Phone and desktop both read/write the same JSONL-backed history so devices
work together instead of siloed localStorage-only chats.

Optional encryption-at-rest (opt-in, off by default): if a passphrase is
configured (via the ``SHARED_MEMORY_PASSPHRASE`` env var), each JSONL line is
stored as an AES-256-GCM envelope instead of plaintext, using the project's
``thinkmesh_core/sync/encryption.py`` primitive. Without a passphrase, behavior
is byte-for-byte unchanged (plaintext JSONL). Reads transparently decrypt and
also tolerate legacy plaintext lines, so enabling encryption never orphans
existing history.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "shared_memory"
DEFAULT_SESSION = "household_default"
_lock = threading.Lock()

# Opt-in passphrase for encryption-at-rest. Empty/unset => plaintext (default).
_PASSPHRASE_ENV = "SHARED_MEMORY_PASSPHRASE"
# Marks an encrypted line so readers can distinguish it from legacy plaintext.
_ENC_PREFIX = "enc:v1:"


def _passphrase() -> Optional[str]:
    pw = os.getenv(_PASSPHRASE_ENV)
    return pw if pw else None


def _get_encryptor():
    """Return a cached AESEncryptor, or None if encryption is disabled.

    The key is derived once (PBKDF2, 200k iters) and reused for every line, so
    per-line encrypt/decrypt stays microsecond-fast while retaining full KDF
    strength. Returns None if no passphrase is set or the primitive is missing.
    """
    pw = _passphrase()
    if not pw:
        return None
    cached = getattr(_get_encryptor, "_cache", None)
    if cached is not None and cached[0] == pw:
        return cached[1]
    try:
        from thinkmesh_core.sync.encryption import AESEncryptor
    except Exception:
        # Fall back to a direct file load: the top-level thinkmesh_core package
        # has a pre-existing eager-import error unrelated to this module.
        try:
            import importlib.util
            import sys as _sys

            enc_path = ROOT / "thinkmesh_core" / "sync" / "encryption.py"
            spec = importlib.util.spec_from_file_location("_shm_enc", enc_path)
            mod = importlib.util.module_from_spec(spec)
            _sys.modules["_shm_enc"] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            AESEncryptor = mod.AESEncryptor
        except Exception:
            return None
    enc = _CachedKeyEncryptor(AESEncryptor(pw))
    _get_encryptor._cache = (pw, enc)  # type: ignore[attr-defined]
    return enc


class _CachedKeyEncryptor:
    """Derive the AES key once, then do fast per-line AES-GCM.

    Wraps AESEncryptor to avoid a 200k-iteration PBKDF2 per line (which would
    make reading a session take seconds). One fixed salt/key is derived up front;
    each line gets its own random nonce, preserving AES-GCM security.
    """

    def __init__(self, base_encryptor: Any) -> None:
        self._base = base_encryptor
        # Derive a single reusable key from a fixed per-instance salt.
        self._salt = os.urandom(base_encryptor.config.salt_len)
        self._key = base_encryptor._derive_key(self._salt)

    def encrypt_line(self, obj: Dict[str, Any]) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)
        plaintext = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        ct = AESGCM(self._key).encrypt(nonce, plaintext, None)
        blob = base64.b64encode(self._salt + nonce + ct).decode("ascii")
        return _ENC_PREFIX + blob

    def decrypt_line(self, line: str) -> Optional[Dict[str, Any]]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        raw = base64.b64decode(line[len(_ENC_PREFIX):])
        salt_len = self._base.config.salt_len
        salt = raw[:salt_len]
        nonce = raw[salt_len : salt_len + 12]
        ct = raw[salt_len + 12 :]
        # Reuse the cached key when the salt matches; otherwise derive on demand
        # (e.g. lines written by a different instance/salt but same passphrase).
        key = self._key if salt == self._salt else self._base._derive_key(salt)
        plaintext = AESGCM(key).decrypt(nonce, ct, None)
        return json.loads(plaintext.decode("utf-8"))


def _session_path(session_id: str) -> Path:
    safe = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (session_id or DEFAULT_SESSION)
    )
    return DATA / f"{safe}.jsonl"


def _meta_path(session_id: str) -> Path:
    safe = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (session_id or DEFAULT_SESSION)
    )
    return DATA / f"{safe}.meta.json"


def append_turn(
    role: str,
    text: str,
    *,
    session_id: str = DEFAULT_SESSION,
    member_id: str = "primary",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    role = (role or "user").strip().lower()
    if role not in ("user", "assistant", "system"):
        role = "user"
    entry = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "role": role,
        "text": text[:8000],
        "member_id": member_id or "primary",
        "meta": meta or {},
    }
    path = _session_path(session_id)
    enc = _get_encryptor()
    with _lock:
        DATA.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            if enc is not None:
                f.write(enc.encrypt_line(entry) + "\n")
            else:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        meta_p = _meta_path(session_id)
        meta_p.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "updated_at": time.time(),
                    "path": str(path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return {"ok": True, "entry": entry}


def recent_turns(
    session_id: str = DEFAULT_SESSION,
    *,
    limit: int = 24,
    member_id: Optional[str] = None,
    include_shared: bool = True,
) -> List[Dict[str, Any]]:
    path = _session_path(session_id)
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    enc = _get_encryptor()
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(_ENC_PREFIX):
                    # Encrypted line: decrypt if we have the passphrase, else skip.
                    if enc is None:
                        continue
                    try:
                        row = enc.decrypt_line(line)
                        if row is not None:
                            rows.append(row)
                    except Exception:
                        continue
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    if member_id:
        filtered = []
        for r in rows:
            mid = r.get("member_id") or "primary"
            wall = (r.get("meta") or {}).get("privacy")
            if wall in ("shared", "family_board") and include_shared:
                filtered.append(r)
            elif mid == member_id:
                filtered.append(r)
        rows = filtered
    return rows[-max(1, min(int(limit or 24), 100)) :]


def context_block(
    session_id: str = DEFAULT_SESSION,
    *,
    limit: int = 12,
    member_id: Optional[str] = None,
    companion: str = "Soul",
) -> str:
    turns = recent_turns(session_id, limit=limit, member_id=member_id)
    if not turns:
        return ""
    lines = ["Shared memory (recent):"]
    for t in turns:
        who = "User" if t.get("role") == "user" else companion
        mid = t.get("member_id")
        prefix = f"{who}" if mid in (None, "primary") else f"{who}[{mid}]"
        lines.append(f"{prefix}: {t.get('text')}")
    return "\n".join(lines)


def clear_session(session_id: str = DEFAULT_SESSION) -> Dict[str, Any]:
    path = _session_path(session_id)
    meta = _meta_path(session_id)
    with _lock:
        if path.is_file():
            path.unlink()
        if meta.is_file():
            meta.unlink()
    return {"ok": True, "cleared": session_id}


def status(session_id: str = DEFAULT_SESSION) -> Dict[str, Any]:
    turns = recent_turns(session_id, limit=500)
    return {
        "ok": True,
        "session_id": session_id,
        "turns": len(turns),
        "path": str(_session_path(session_id)),
    }
