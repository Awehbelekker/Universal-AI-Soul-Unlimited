"""
Unit tests for AES-256-GCM encryption-at-rest.

Verifies real authenticated encryption: round-trips, wrong-passphrase rejection,
tamper detection, JSON helpers, and file round-trips. Loaded by direct file path
to bypass the pre-existing eager import in thinkmesh_core/__init__.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

_spec = importlib.util.spec_from_file_location(
    "encryption_under_test",
    project_root / "thinkmesh_core" / "sync" / "encryption.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

AESEncryptor = _mod.AESEncryptor
EncryptionConfig = _mod.EncryptionConfig
EncryptionError = _mod.EncryptionError

# Use a low iteration count in tests so key derivation stays fast.
_FAST = EncryptionConfig(iterations=1000)


def test_round_trip_bytes():
    enc = AESEncryptor("correct horse battery staple", _FAST)
    plaintext = b"secret memory contents"
    envelope = enc.encrypt(plaintext)
    assert envelope != plaintext
    assert enc.decrypt(envelope) == plaintext


def test_round_trip_str():
    enc = AESEncryptor("passphrase", _FAST)
    assert enc.decrypt(enc.encrypt("hello world")) == b"hello world"


def test_ciphertext_differs_each_time():
    enc = AESEncryptor("passphrase", _FAST)
    a = enc.encrypt("same input")
    b = enc.encrypt("same input")
    # Random salt + nonce mean envelopes must differ.
    assert a != b
    assert enc.decrypt(a) == enc.decrypt(b) == b"same input"


def test_wrong_passphrase_fails():
    envelope = AESEncryptor("right-pass", _FAST).encrypt("data")
    with pytest.raises(EncryptionError):
        AESEncryptor("wrong-pass", _FAST).decrypt(envelope)


def test_tamper_detection():
    enc = AESEncryptor("passphrase", _FAST)
    envelope = bytearray(enc.encrypt("integrity matters"))
    envelope[-1] ^= 0x01  # Flip a bit in the ciphertext/tag.
    with pytest.raises(EncryptionError):
        enc.decrypt(bytes(envelope))


def test_invalid_envelope_header():
    enc = AESEncryptor("passphrase", _FAST)
    with pytest.raises(EncryptionError):
        enc.decrypt(b"not-a-valid-envelope")


def test_empty_passphrase_rejected():
    with pytest.raises(EncryptionError):
        AESEncryptor("", _FAST)


def test_json_round_trip():
    enc = AESEncryptor("passphrase", _FAST)
    obj = {"user": "ian", "notes": ["a", "b"], "n": 3}
    assert enc.decrypt_json(enc.encrypt_json(obj)) == obj


def test_file_round_trip(tmp_path):
    enc = AESEncryptor("passphrase", _FAST)
    target = tmp_path / "vault" / "data.enc"
    obj = {"conversation": [{"role": "user", "text": "hi"}]}
    enc.encrypt_file(target, obj)
    assert target.exists()
    # Stored bytes must not contain the plaintext.
    assert b"conversation" not in target.read_bytes()
    assert enc.decrypt_file_json(target) == obj
