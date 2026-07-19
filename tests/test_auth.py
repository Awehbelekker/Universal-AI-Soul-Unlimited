"""Unit tests for the local-first auth token module.

Deterministic: a fixed signing secret and injected ``now`` timestamps make
issuance/expiry reproducible without sleeping. Audit emission is redirected into
tmp_path so verification of the emitted auth events touches no real data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.security import audit_logger as al  # noqa: E402
from core.security import auth  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv(auth._SECRET_ENV, "unit-test-secret")
    monkeypatch.setattr(al, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(al, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.delenv(al._PASSPHRASE_ENV, raising=False)
    al._reset_cache()
    yield
    al._reset_cache()


def test_issue_verify_round_trip_preserves_claims():
    tok = auth.issue_token("ian", roles=["admin", "user"], ttl_seconds=60, now=1000)
    payload = auth.verify_token(tok, now=1030)
    assert payload["sub"] == "ian"
    assert payload["roles"] == ["admin", "user"]
    assert payload["iat"] == 1000
    assert payload["exp"] == 1060
    assert "jti" in payload


def test_token_is_three_part_compact_string():
    tok = auth.issue_token("sam", now=1000)
    assert tok.count(".") == 2
    assert all(part for part in tok.split("."))


def test_expired_token_rejected():
    tok = auth.issue_token("ian", ttl_seconds=10, now=1000)
    with pytest.raises(auth.TokenError, match="expired"):
        auth.verify_token(tok, now=1011)


def test_expiry_is_exclusive_at_boundary():
    tok = auth.issue_token("ian", ttl_seconds=10, now=1000)
    # exp == 1010; current == exp must be treated as expired.
    with pytest.raises(auth.TokenError, match="expired"):
        auth.verify_token(tok, now=1010)
    # one second before is still valid.
    assert auth.verify_token(tok, now=1009)["sub"] == "ian"


def test_tampered_payload_rejected():
    tok = auth.issue_token("ian", roles=["user"], now=1000)
    h, p, sig = tok.split(".")
    forged = f"{h}.{p}xx.{sig}"
    with pytest.raises(auth.TokenError):
        auth.verify_token(forged, now=1010)


def test_wrong_secret_rejected(monkeypatch):
    tok = auth.issue_token("ian", now=1000)
    monkeypatch.setenv(auth._SECRET_ENV, "a-different-secret")
    with pytest.raises(auth.TokenError, match="bad signature"):
        auth.verify_token(tok, now=1010)


def test_malformed_token_rejected():
    for bad in ("", "abc", "a.b", "a.b.c.d"):
        with pytest.raises(auth.TokenError):
            auth.verify_token(bad, now=1010)


def test_extra_claims_cannot_override_structural_fields():
    tok = auth.issue_token(
        "ian", ttl_seconds=60, now=1000,
        extra={"sub": "attacker", "exp": 9_999_999_999, "org": "acme"},
    )
    payload = auth.verify_token(tok, now=1030)
    assert payload["sub"] == "ian"  # not overridden
    assert payload["exp"] == 1060  # not overridden
    assert payload["org"] == "acme"  # non-reserved extra allowed


def test_audit_events_emitted_on_issue_and_verify():
    tok = auth.issue_token("ian", now=1000)
    auth.verify_token(tok, now=1010)
    issue = al.query(category="auth", action="token_issue")
    verify_ok = al.query(category="auth", action="token_verify", outcome="success")
    assert len(issue) == 1 and issue[0]["actor"] == "ian"
    assert len(verify_ok) == 1 and verify_ok[0]["actor"] == "ian"


def test_audit_failure_event_on_bad_verify():
    tok = auth.issue_token("ian", ttl_seconds=1, now=1000)
    with pytest.raises(auth.TokenError):
        auth.verify_token(tok, now=5000)
    failures = al.query(category="auth", action="token_verify", outcome="failure")
    assert len(failures) == 1
    assert failures[0]["severity"] == "warning"
