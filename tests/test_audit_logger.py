"""Unit tests for the local-first audit logger.

Focus: plaintext-by-default (local-first), opt-in AES-256-GCM at rest with no
plaintext leakage, tolerant mixed-line reads, privacy redaction, and query
filters. Deterministic and offline.

The module is imported normally (it only uses stdlib + a file-path fallback for
the crypto primitive), but the on-disk paths and the cached encryptor are
redirected/reset per test so nothing touches the real data/audit directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.security import audit_logger as al  # noqa: E402

_PASS = al._PASSPHRASE_ENV


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect audit storage to a temp dir and reset the encryptor cache."""
    monkeypatch.setattr(al, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(al, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.delenv(_PASS, raising=False)
    al._reset_cache()
    yield
    al._reset_cache()


def test_plaintext_default_round_trip():
    al.log_event("login", category="auth", actor="ian", target="ui")
    disk = al.AUDIT_LOG.read_text(encoding="utf-8")
    assert "login" in disk and al._ENC_PREFIX not in disk
    events = al.read_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["action"] == "login"
    assert ev["category"] == "auth"
    assert ev["actor"] == "ian"
    assert ev["target"] == "ui"
    assert ev["outcome"] == "success"
    assert "id" in ev and "ts" in ev


def test_unknown_category_normalized_to_system():
    ev = al.log_event("x", category="not_a_category")
    assert ev["category"] == "system"


def test_privacy_redaction_nested(monkeypatch):
    al.log_event(
        "config_change",
        category="config",
        detail={
            "password": "hunter2",
            "api_key": "sk-123",
            "nested": {"token": "abc", "keep": "ok"},
            "items": [{"secret": "s"}, {"safe": 1}],
        },
    )
    disk = al.AUDIT_LOG.read_bytes()
    for leaked in (b"hunter2", b"sk-123", b"abc"):
        assert leaked not in disk
    d = al.read_events()[0]["detail"]
    assert d["password"] == al._REDACTED
    assert d["api_key"] == al._REDACTED
    assert d["nested"]["token"] == al._REDACTED
    assert d["nested"]["keep"] == "ok"
    assert d["items"][0]["secret"] == al._REDACTED
    assert d["items"][1]["safe"] == 1


def test_encrypted_round_trip_no_plaintext(monkeypatch):
    monkeypatch.setenv(_PASS, "audit-pass")
    al._reset_cache()
    al.log_event("read_file", category="data_access", target="notes.txt")
    raw = al.AUDIT_LOG.read_bytes()
    assert al._ENC_PREFIX.encode() in raw
    assert b"read_file" not in raw and b"notes.txt" not in raw
    events = al.read_events()
    assert len(events) == 1
    assert isinstance(events[0], dict)
    assert events[0]["action"] == "read_file"
    assert events[0]["target"] == "notes.txt"


def test_wrong_passphrase_yields_nothing(monkeypatch):
    monkeypatch.setenv(_PASS, "right-pass")
    al._reset_cache()
    al.log_event("secret_action", category="security")
    monkeypatch.setenv(_PASS, "wrong-pass")
    al._reset_cache()
    assert al.read_events() == []


def test_no_passphrase_skips_encrypted_lines(monkeypatch):
    monkeypatch.setenv(_PASS, "pass")
    al._reset_cache()
    al.log_event("enc_only", category="security")
    monkeypatch.delenv(_PASS, raising=False)
    al._reset_cache()
    assert al.read_events() == []


def test_legacy_plaintext_readable_after_enabling(monkeypatch):
    al.log_event("legacy", category="system")
    monkeypatch.setenv(_PASS, "pass")
    al._reset_cache()
    al.log_event("encrypted", category="security")
    actions = [e["action"] for e in al.read_events()]
    assert actions == ["legacy", "encrypted"]


def test_query_filters_and_time_window():
    a = al.log_event("login", category="auth", actor="ian")
    al.log_event("logout", category="auth", actor="sam")
    al.log_event("write", category="data_access", actor="ian")
    assert len(al.query(category="auth")) == 2
    assert len(al.query(actor="ian")) == 2
    assert len(al.query(category="auth", actor="ian")) == 1
    assert len(al.query(action="write")) == 1
    # since strictly after the first event excludes it.
    later = al.query(since=a["ts"] + 1000)
    assert later == []


def test_tail_and_limit_ordering():
    for i in range(5):
        al.log_event(f"e{i}", category="system")
    last3 = al.tail(3)
    assert [e["action"] for e in last3] == ["e2", "e3", "e4"]
    assert al.read_events(limit=2)[0]["action"] == "e3"


def test_read_events_tolerates_corrupt_lines():
    al.log_event("good", category="system")
    with al.AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write("this is not json\n")
    events = al.read_events()
    assert len(events) == 1 and events[0]["action"] == "good"


def test_log_event_never_raises(monkeypatch):
    # Point the log at an un-writable path (a dir) => write fails silently.
    monkeypatch.setattr(al, "AUDIT_LOG", al.AUDIT_DIR)
    ev = al.log_event("x", category="system")
    assert ev["action"] == "x"  # still returns the event dict
