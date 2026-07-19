"""Local-first authentication tokens (JWT-style, stdlib only).

A self-contained signed-token scheme for gating local/enterprise features
without pulling in an external JWT library or an external identity provider —
consistent with the project's local-first, minimal-dependency stance.

Tokens are compact ``header.payload.signature`` strings (base64url), signed with
**HMAC-SHA256**. The signing secret comes from ``AUTH_SIGNING_SECRET``; if unset,
an ephemeral per-process secret is generated (tokens then survive only for the
life of the process — fine for a single local session, and it fails safe rather
than using a hard-coded key).

Public API: :func:`issue_token`, :func:`verify_token`, :class:`TokenError`.
Verification checks signature (constant-time), structure, and expiry, and emits
``auth`` audit events. There is no server round-trip — this is symmetric, local
verification only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

_SECRET_ENV = "AUTH_SIGNING_SECRET"
_ALG = "HS256"
_DEFAULT_TTL_SECONDS = 3600  # 1 hour

# Ephemeral fallback secret, generated once per process when the env is unset.
_EPHEMERAL_SECRET = os.urandom(32)


class TokenError(Exception):
    """Raised when a token is malformed, mis-signed, or expired."""


def _secret() -> bytes:
    env = os.getenv(_SECRET_ENV)
    return env.encode("utf-8") if env else _EPHEMERAL_SECRET


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


def _sign(signing_input: bytes) -> str:
    sig = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _audit(action: str, subject: str, outcome: str) -> None:
    """Emit an auth audit event. Never breaks the caller."""
    try:
        from core.security import log_event

        log_event(
            action,
            category="auth",
            actor=subject or "unknown",
            target="token",
            outcome=outcome,
            severity="warning" if outcome == "failure" else "info",
        )
    except Exception:
        pass


def issue_token(
    subject: str,
    *,
    roles: Optional[List[str]] = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    extra: Optional[Dict[str, Any]] = None,
    now: Optional[float] = None,
) -> str:
    """Issue a signed token for ``subject``. ``now`` is injectable for tests."""
    issued = int(now if now is not None else time.time())
    header = {"alg": _ALG, "typ": "JWT"}
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "roles": list(roles or []),
        "iat": issued,
        "exp": issued + int(ttl_seconds),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        # Reserved claims win; extra can't override structural fields.
        for k, v in extra.items():
            payload.setdefault(k, v)
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    token = f"{h}.{p}.{_sign(signing_input)}"
    _audit("token_issue", str(subject), "success")
    return token


def verify_token(token: str, *, now: Optional[float] = None) -> Dict[str, Any]:
    """Verify a token and return its payload, or raise :class:`TokenError`.

    Checks structure, HMAC signature (constant-time), and expiry. Emits an
    ``auth`` audit event for both success and failure. ``now`` is injectable.
    """
    try:
        parts = (token or "").split(".")
        if len(parts) != 3:
            raise TokenError("malformed token")
        h, p, sig = parts
        signing_input = f"{h}.{p}".encode("ascii")
        expected = _sign(signing_input)
        if not hmac.compare_digest(expected, sig):
            raise TokenError("bad signature")
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
        if not isinstance(payload, dict):
            raise TokenError("bad payload")
        current = int(now if now is not None else time.time())
        exp = int(payload.get("exp", 0))
        if current >= exp:
            raise TokenError("token expired")
    except TokenError as exc:
        sub = ""
        try:
            sub = json.loads(_b64url_decode((token or "..").split(".")[1]))\
                .get("sub", "")
        except Exception:
            pass
        _audit("token_verify", str(sub), "failure")
        raise exc
    except Exception as exc:  # any decode/parse error => invalid token
        _audit("token_verify", "", "failure")
        raise TokenError(f"invalid token: {exc}") from exc
    _audit("token_verify", str(payload.get("sub", "")), "success")
    return payload
