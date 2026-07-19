"""
Tests for opt-in encryption-at-rest of shared session memory.

Verifies the local-first default (no passphrase => plaintext JSONL, unchanged),
that enabling a passphrase encrypts on disk and round-trips correctly, that a
wrong passphrase yields no readable turns, and that legacy plaintext lines
remain readable after encryption is enabled.

Loaded by direct file path to bypass the pre-existing eager import in
thinkmesh_core/__init__.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

_spec = importlib.util.spec_from_file_location(
    "shared_session_under_test",
    project_root / "core" / "memory" / "shared_session.py",
)
shm = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = shm
_spec.loader.exec_module(shm)


def _reset_cache():
    """Drop the cached encryptor so a new passphrase takes effect."""
    if hasattr(shm._get_encryptor, "_cache"):
        delattr(shm._get_encryptor, "_cache")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect the data dir to a temp path and reset the encryptor cache."""
    monkeypatch.setattr(shm, "DATA", tmp_path / "shared_memory")
    monkeypatch.delenv(shm._PASSPHRASE_ENV, raising=False)
    _reset_cache()
    yield
    _reset_cache()


def test_plaintext_default_roundtrip():
    shm.append_turn("user", "hello world", session_id="s1")
    turns = shm.recent_turns("s1")
    assert len(turns) == 1 and turns[0]["text"] == "hello world"
    # On-disk file is plaintext JSONL (no encryption prefix).
    data = shm._session_path("s1").read_text(encoding="utf-8")
    assert "hello world" in data
    assert shm._ENC_PREFIX not in data


def test_encrypted_roundtrip(monkeypatch):
    monkeypatch.setenv(shm._PASSPHRASE_ENV, "correct horse")
    _reset_cache()

    shm.append_turn("user", "secret message", session_id="s2")
    shm.append_turn("assistant", "secret reply", session_id="s2")

    # On disk: encrypted lines, and the plaintext must NOT appear.
    raw = shm._session_path("s2").read_bytes()
    assert shm._ENC_PREFIX.encode() in raw
    assert b"secret message" not in raw
    assert b"secret reply" not in raw

    # Reading back with the same passphrase decrypts transparently.
    turns = shm.recent_turns("s2")
    assert [t["text"] for t in turns] == ["secret message", "secret reply"]


def test_wrong_passphrase_yields_nothing(monkeypatch):
    monkeypatch.setenv(shm._PASSPHRASE_ENV, "right-pass")
    _reset_cache()
    shm.append_turn("user", "classified", session_id="s3")

    # Switch to a different passphrase: encrypted lines must not decrypt.
    monkeypatch.setenv(shm._PASSPHRASE_ENV, "wrong-pass")
    _reset_cache()
    turns = shm.recent_turns("s3")
    assert turns == []


def test_no_passphrase_skips_encrypted_lines(monkeypatch):
    # Write encrypted, then read with no passphrase set.
    monkeypatch.setenv(shm._PASSPHRASE_ENV, "pw")
    _reset_cache()
    shm.append_turn("user", "hidden", session_id="s4")

    monkeypatch.delenv(shm._PASSPHRASE_ENV, raising=False)
    _reset_cache()
    # No passphrase => encrypted lines are skipped (not crashing, not leaking).
    assert shm.recent_turns("s4") == []


def test_legacy_plaintext_still_readable_after_enabling(monkeypatch):
    # Existing plaintext history written before encryption was enabled.
    shm.append_turn("user", "old plain turn", session_id="s5")

    # Enable encryption and append a new turn.
    monkeypatch.setenv(shm._PASSPHRASE_ENV, "pw")
    _reset_cache()
    shm.append_turn("assistant", "new encrypted turn", session_id="s5")

    # Both the legacy plaintext and the new encrypted line are returned in order.
    turns = shm.recent_turns("s5")
    assert [t["text"] for t in turns] == ["old plain turn", "new encrypted turn"]


def test_context_block_reflects_encrypted_turns(monkeypatch):
    monkeypatch.setenv(shm._PASSPHRASE_ENV, "pw")
    _reset_cache()
    shm.append_turn("user", "what is the weather", session_id="s6")
    block = shm.context_block("s6")
    assert "what is the weather" in block
