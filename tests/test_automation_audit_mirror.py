"""Tests that automation audit entries mirror into the unified security trail.

The existing per-action automation log (data/automation_audit.jsonl) is left
untouched; append_audit() additionally emits a category='automation' event into
the unified audit trail. Both logs are redirected into tmp_path here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.automation import real_actions as ra  # noqa: E402
from core.security import audit_logger as al  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(al, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(al, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr(ra, "AUDIT_LOG", tmp_path / "automation_audit.jsonl")
    monkeypatch.delenv(al._PASSPHRASE_ENV, raising=False)
    al._reset_cache()
    yield
    al._reset_cache()


def test_success_entry_mirrors_as_automation_event():
    ra.append_audit(
        {
            "action": "write_note",
            "source": "smoke",
            "success": True,
            "consent": True,
            "path": "/tmp/note.txt",
            "description": "a note",
        }
    )
    # Original automation log still written.
    lines = ra.AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["action"] == "write_note"
    # Mirrored into the unified trail.
    events = al.query(category="automation")
    assert len(events) == 1
    ev = events[0]
    assert ev["action"] == "write_note"
    assert ev["actor"] == "smoke"
    assert ev["outcome"] == "success"
    assert ev["target"] == "/tmp/note.txt"
    assert ev["detail"]["consent"] is True
    assert ev["detail"]["description"] == "a note"


def test_failure_entry_mirrors_with_failure_outcome():
    ra.append_audit(
        {
            "action": "delete_file",
            "source": "coact",
            "success": False,
            "consent": True,
            "error_message": "boom",
        }
    )
    events = al.query(category="automation")
    assert len(events) == 1
    ev = events[0]
    assert ev["outcome"] == "failure"
    assert ev["severity"] == "warning"
    assert ev["target"] is None
    assert ev["detail"]["error_message"] == "boom"


def test_dest_used_as_target_when_no_path():
    ra.append_audit(
        {"action": "copy_file", "source": "coact", "success": True,
         "dest": "/tmp/dest.txt"}
    )
    ev = al.query(category="automation")[0]
    assert ev["target"] == "/tmp/dest.txt"


def test_mirror_never_breaks_append_audit(monkeypatch):
    import core.security as security

    def _boom(*_a, **_k):
        raise RuntimeError("audit down")

    monkeypatch.setattr(security, "log_event", _boom)
    # Must not raise, and the original automation log must still be written.
    ra.append_audit({"action": "mkdir", "source": "coact", "success": True})
    assert ra.AUDIT_LOG.is_file()
    assert json.loads(ra.AUDIT_LOG.read_text().splitlines()[0])["action"] == "mkdir"
