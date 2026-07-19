#!/usr/bin/env python3
"""Smoke: the three adopted integrations, end-to-end, offline (no network).

1. Encryption-at-rest for shared session memory (opt-in via passphrase).
2. Ollama auto-optimization (hardware-aware runtime options on init).
3. Phase2 honest accelerator detection (TensorRT/NNAPI probed, not assumed).
4. Local-first audit logging (plaintext default, privacy redaction, opt-in AES).
5. Enterprise auth (local-first HMAC-SHA256 JWT-style tokens, stdlib only).

Run: python scripts/smoke_adoption.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_by_path(name: str, rel: str):
    """Load a module by file path (bypasses the broken top-level package)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def check_encryption() -> None:
    shm = _load_by_path("shm_smoke", "core/memory/shared_session.py")

    def _reset_cache() -> None:
        if hasattr(shm._get_encryptor, "_cache"):
            delattr(shm._get_encryptor, "_cache")

    # Plaintext default (no passphrase): unchanged behavior.
    os.environ.pop(shm._PASSPHRASE_ENV, None)
    _reset_cache()
    shm.clear_session("smoke_enc")
    shm.append_turn("user", "plain hello", session_id="smoke_enc")
    disk = shm._session_path("smoke_enc").read_text(encoding="utf-8")
    assert "plain hello" in disk and shm._ENC_PREFIX not in disk

    # Enable encryption: on-disk bytes must not contain plaintext, round-trips.
    os.environ[shm._PASSPHRASE_ENV] = "smoke-pass"
    _reset_cache()
    shm.append_turn("assistant", "secret reply", session_id="smoke_enc")
    raw = shm._session_path("smoke_enc").read_bytes()
    assert shm._ENC_PREFIX.encode() in raw
    assert b"secret reply" not in raw
    texts = [t["text"] for t in shm.recent_turns("smoke_enc")]
    assert texts == ["plain hello", "secret reply"]

    # Cleanup.
    shm.clear_session("smoke_enc")
    os.environ.pop(shm._PASSPHRASE_ENV, None)
    _reset_cache()
    print("encryption ok (plaintext default + opt-in AES round-trip)")


def check_ollama_autooptimize() -> None:
    from core.engines.ollama_integration import (
        OllamaIntegration,
        _detect_runtime_options,
    )

    detected = _detect_runtime_options()
    assert isinstance(detected, dict)

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"response": "ok", "eval_count": 1}

    class _FakeClient:
        def __init__(self):
            self.last_json = None

        async def post(self, url, json=None):
            self.last_json = json
            return _FakeResponse()

        async def aclose(self):
            pass

    async def _run() -> None:
        integ = OllamaIntegration(auto_optimize=True)
        integ.client = _FakeClient()
        integ.model_loaded = True
        # Explicit generation args + auto-detected base options coexist.
        await integ.generate("hi", max_tokens=32, num_ctx=777)
        opts = integ.client.last_json["options"]
        assert opts["num_predict"] == 32
        # Explicit kwarg overrides any auto-detected base value.
        assert opts["num_ctx"] == 777

        # auto_optimize=False => no hardware base keys injected.
        integ2 = OllamaIntegration(auto_optimize=False)
        integ2.client = _FakeClient()
        integ2.model_loaded = True
        await integ2.generate("hi", max_tokens=16)
        assert integ2.runtime_options == {}

    asyncio.run(_run())
    print(f"ollama ok (auto options={detected or 'defaults'})")


def check_phase2_detection() -> None:
    p2 = _load_by_path("phase2_smoke", "thinkmesh_core/localai/phase2_optimizer.py")
    opt = p2.Phase2Optimizer()
    caps = opt.get_capabilities()
    for key in ("platform", "active_accelerator", "available", "tensorrt", "nnapi"):
        assert key in caps
    # Honesty: TensorRT is only present if genuinely probed.
    trt_present = p2.AcceleratorType.TENSORRT.value in opt.available_accelerators
    assert caps["tensorrt"]["available"] == trt_present
    # optimize_* return an error dict when the accelerator is unavailable.
    if not trt_present:
        assert "error" in opt.optimize_for_tensorrt("m.onnx")
    print(
        "phase2 ok "
        f"(active={caps['active_accelerator']}, "
        f"tensorrt={caps['tensorrt']['available']}, "
        f"nnapi={caps['nnapi']['available']})"
    )


def check_audit_logging() -> None:
    al = _load_by_path("audit_smoke", "core/security/audit_logger.py")

    import tempfile

    tmp = Path(tempfile.mkdtemp())
    al.AUDIT_DIR = tmp
    al.AUDIT_LOG = tmp / "audit.jsonl"

    # Plaintext default + privacy redaction: secret never hits disk.
    os.environ.pop(al._PASSPHRASE_ENV, None)
    al._reset_cache()
    al.log_event("login", category="auth", actor="ian", detail={"password": "pw"})
    disk = al.AUDIT_LOG.read_text(encoding="utf-8")
    assert "login" in disk and al._ENC_PREFIX not in disk and "pw" not in disk
    assert al.read_events()[0]["detail"]["password"] == al._REDACTED

    # Opt-in encryption: plaintext absent from disk bytes, decrypt round-trips.
    os.environ[al._PASSPHRASE_ENV] = "audit-pass"
    al._reset_cache()
    al.log_event("read_file", category="data_access", target="notes.txt")
    raw = al.AUDIT_LOG.read_bytes()
    assert al._ENC_PREFIX.encode() in raw and b"read_file" not in raw
    actions = [e["action"] for e in al.read_events()]
    assert actions == ["login", "read_file"]  # legacy plaintext + encrypted
    assert len(al.query(category="auth")) == 1

    os.environ.pop(al._PASSPHRASE_ENV, None)
    al._reset_cache()
    print("audit ok (plaintext default + redaction + opt-in AES round-trip)")


def check_auth_tokens() -> None:
    from core.security import auth

    os.environ[auth._SECRET_ENV] = "smoke-secret"
    tok = auth.issue_token("smoke_user", roles=["user"], ttl_seconds=60, now=1000)
    payload = auth.verify_token(tok, now=1010)
    assert payload["sub"] == "smoke_user" and payload["roles"] == ["user"]
    # Expiry and tamper are rejected.
    try:
        auth.verify_token(tok, now=2000)
        raise AssertionError("expired token should have been rejected")
    except auth.TokenError:
        pass
    try:
        auth.verify_token(tok[:-2] + "zz", now=1010)
        raise AssertionError("tampered token should have been rejected")
    except auth.TokenError:
        pass
    os.environ.pop(auth._SECRET_ENV, None)
    print("auth ok (issue/verify + expiry + tamper rejection)")


def main() -> int:
    check_encryption()
    check_ollama_autooptimize()
    check_phase2_detection()
    check_audit_logging()
    check_auth_tokens()
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
