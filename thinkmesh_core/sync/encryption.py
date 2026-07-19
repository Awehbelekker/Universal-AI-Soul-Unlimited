"""
AES-256 Encryption-at-Rest (local-first)
=========================================

Genuine authenticated encryption for locally stored data (conversation history,
memories, backup payloads). Uses AES-256-GCM with a per-encryption random nonce
and PBKDF2-HMAC-SHA256 key derivation from a user passphrase.

Note on provenance: the reference `universal-soul-ai/.../encrypted_backup.py`
used XOR "encryption", which is NOT secure (trivially reversible and unauthen-
ticated). Per DOC_TRUST.md we did NOT adopt it; this module implements real
AES-256-GCM via the `cryptography` package (already a declared dependency).

Envelope format (bytes): MAGIC(4) | VERSION(1) | SALT(16) | NONCE(12) | CIPHERTEXT
where CIPHERTEXT includes the GCM authentication tag.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

_MAGIC = b"USAE"          # Universal Soul AES Envelope
_VERSION = 1
_SALT_LEN = 16
_NONCE_LEN = 12           # 96-bit nonce recommended for GCM
_KEY_LEN = 32             # AES-256
_PBKDF2_ITERATIONS = 200_000


@dataclass
class EncryptionConfig:
    """Key-derivation parameters for encryption-at-rest."""

    iterations: int = _PBKDF2_ITERATIONS
    salt_len: int = _SALT_LEN


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


class AESEncryptor:
    """AES-256-GCM authenticated encryption with PBKDF2 key derivation."""

    def __init__(self, passphrase: str, config: Optional[EncryptionConfig] = None) -> None:
        if not passphrase:
            raise EncryptionError("A non-empty passphrase is required")
        self._passphrase = passphrase.encode("utf-8")
        self.config = config or EncryptionConfig()

    def _derive_key(self, salt: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_LEN,
            salt=salt,
            iterations=self.config.iterations,
        )
        return kdf.derive(self._passphrase)

    def encrypt(self, plaintext: Union[bytes, str]) -> bytes:
        """Encrypt bytes/str into a self-describing envelope."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        try:
            salt = os.urandom(self.config.salt_len)
            nonce = os.urandom(_NONCE_LEN)
            key = self._derive_key(salt)
            ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
            return _MAGIC + bytes([_VERSION]) + salt + nonce + ciphertext
        except Exception as e:  # pragma: no cover - defensive
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, envelope: bytes) -> bytes:
        """Decrypt an envelope produced by encrypt(); verifies authenticity."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        header = len(_MAGIC) + 1 + self.config.salt_len + _NONCE_LEN
        if len(envelope) < header or envelope[: len(_MAGIC)] != _MAGIC:
            raise EncryptionError("Invalid or corrupted envelope header")
        version = envelope[len(_MAGIC)]
        if version != _VERSION:
            raise EncryptionError(f"Unsupported envelope version: {version}")
        offset = len(_MAGIC) + 1
        salt = envelope[offset : offset + self.config.salt_len]
        offset += self.config.salt_len
        nonce = envelope[offset : offset + _NONCE_LEN]
        offset += _NONCE_LEN
        ciphertext = envelope[offset:]
        try:
            key = self._derive_key(salt)
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as e:
            # Wrong passphrase or tampering both surface here.
            raise EncryptionError(f"Decryption failed (wrong key or tampered data): {e}") from e

    def encrypt_json(self, obj: Any) -> bytes:
        """Serialize an object to JSON and encrypt it."""
        return self.encrypt(json.dumps(obj, sort_keys=True))

    def decrypt_json(self, envelope: bytes) -> Any:
        """Decrypt an envelope and parse it as JSON."""
        return json.loads(self.decrypt(envelope).decode("utf-8"))

    def encrypt_file(self, path: Union[str, Path], data: Union[bytes, str, Any]) -> Path:
        """Encrypt data and write the envelope to `path` (JSON if not bytes/str)."""
        path = Path(path)
        payload = (
            data if isinstance(data, (bytes, str)) else json.dumps(data, sort_keys=True)
        )
        envelope = self.encrypt(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(envelope)
        logger.info("Wrote encrypted file (%d bytes) to %s", len(envelope), path)
        return path

    def decrypt_file(self, path: Union[str, Path]) -> bytes:
        """Read and decrypt an envelope file, returning plaintext bytes."""
        return self.decrypt(Path(path).read_bytes())

    def decrypt_file_json(self, path: Union[str, Path]) -> Any:
        """Read, decrypt, and JSON-parse an envelope file."""
        return json.loads(self.decrypt_file(path).decode("utf-8"))
