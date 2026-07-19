# Sync Module
__version__ = '1.0.0'

try:
    from .encryption import (
        AESEncryptor,
        EncryptionConfig,
        EncryptionError,
    )
    _ENC_EXPORTS = ['AESEncryptor', 'EncryptionConfig', 'EncryptionError']
except Exception:  # pragma: no cover - defensive import guard
    AESEncryptor = None  # type: ignore
    EncryptionConfig = None  # type: ignore
    EncryptionError = None  # type: ignore
    _ENC_EXPORTS = []

__all__ = _ENC_EXPORTS
