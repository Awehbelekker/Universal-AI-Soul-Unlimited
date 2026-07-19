"""Tests that household PIN verification emits privacy-wall auth audit events.

The audit log path and the household store are both redirected into tmp_path so
nothing touches the real data/ directory. Auditing must never change
verify_member's return contract, only add an audit trail as a side effect.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.family import household  # noqa: E402
from core.security import audit_logger as al  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    # Redirect the audit trail into tmp and reset the encryptor cache.
    monkeypatch.setattr(al, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(al, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.delenv(al._PASSPHRASE_ENV, raising=False)
    al._reset_cache()

    # Redirect the household store into tmp with one PIN-protected member.
    hh_path = tmp_path / "household.json"
    hh_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "name": "Test House",
                "members": [{"id": "sam", "display_name": "Sam", "role": "child",
                             "pin": "1234"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(household, "HOUSEHOLD_PATH", hh_path)
    monkeypatch.setattr(household, "PROFILE_PATH", tmp_path / "profile.json")
    yield
    al._reset_cache()


def test_correct_pin_emits_success_event():
    res = household.verify_member("sam", "1234")
    assert res["ok"] and res["authenticated"] is True  # contract unchanged
    events = al.query(category="auth")
    assert len(events) == 1
    ev = events[0]
    assert ev["action"] == "pin_verify"
    assert ev["actor"] == "sam"
    assert ev["outcome"] == "success"
    assert ev["severity"] == "info"


def test_wrong_pin_emits_failure_event():
    res = household.verify_member("sam", "0000")
    assert res["ok"] is False and res["authenticated"] is False
    events = al.query(category="auth")
    assert len(events) == 1
    assert events[0]["outcome"] == "failure"
    assert events[0]["severity"] == "warning"


def test_unknown_member_emits_failure_event():
    res = household.verify_member("ghost", "1234")
    assert res["ok"] is False and res["authenticated"] is False
    events = al.query(category="auth")
    assert len(events) == 1
    assert events[0]["actor"] == "ghost"
    assert events[0]["outcome"] == "failure"


def test_pin_value_never_written_to_disk():
    household.verify_member("sam", "1234")
    household.verify_member("sam", "0000")
    raw = al.AUDIT_LOG.read_bytes()
    assert b"1234" not in raw and b"0000" not in raw


def test_context_update_emits_config_event():
    household.update_context({"enabled": True, "name": "New Name",
                             "shared_values": ["respect"]})
    events = al.query(category="config")
    assert len(events) == 1
    ev = events[0]
    assert ev["action"] == "context_update"
    assert ev["target"] == "household"
    assert ev["detail"]["fields"] == ["enabled", "name", "shared_values"]


def test_member_add_and_update_emit_config_events():
    household.upsert_member({"display_name": "Kim", "role": "parent", "pin": "9999"})
    add = al.query(category="config", action="member_add")
    assert len(add) == 1
    assert add[0]["target"] == "kim"
    assert add[0]["detail"] == {"role": "parent", "pin_set": True}
    # PIN value must not reach the audit trail.
    assert b"9999" not in al.AUDIT_LOG.read_bytes()

    household.upsert_member({"id": "kim", "display_name": "Kim", "role": "parent"})
    upd = al.query(category="config", action="member_update")
    assert len(upd) == 1 and upd[0]["target"] == "kim"


def test_member_remove_emits_config_event():
    household.upsert_member({"display_name": "Bob", "role": "sibling"})
    household.remove_member("bob")
    rem = al.query(category="config", action="member_remove")
    assert len(rem) == 1 and rem[0]["target"] == "bob"


def test_audit_helper_swallows_errors(monkeypatch):
    # If the underlying log_event blows up, _audit_auth must not propagate it,
    # so verify_member's flow can never be broken by the audit side effect.
    import core.security as security

    def _boom(*_a, **_k):
        raise RuntimeError("audit down")

    # _audit_auth does `from core.security import log_event`, so patch there.
    monkeypatch.setattr(security, "log_event", _boom)
    # Must not raise despite the injected failure.
    household._audit_auth("pin_verify", "sam", "success")
    # And verification still returns its normal contract.
    res = household.verify_member("sam", "1234")
    assert res["ok"] and res["authenticated"] is True
