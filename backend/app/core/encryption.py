"""AES-256-GCM encryption for user credentials storage."""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.exceptions import EncryptionError

# AES-256 requires 32-byte key
_KEY_LENGTH = 32
_NONCE_LENGTH = 12  # standard GCM nonce


def _get_key(key_hex: str) -> bytes:
    """Convert hex-encoded key string to bytes."""
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as e:
        raise EncryptionError(f"Invalid encryption key format: {e}") from e
    if len(key) != _KEY_LENGTH:
        raise EncryptionError(
            f"Encryption key must be {_KEY_LENGTH} bytes ({_KEY_LENGTH * 2} hex chars), "
            f"got {len(key)} bytes"
        )
    return key


def encrypt(plaintext: str, key_hex: str) -> bytes:
    """
    Encrypt a string using AES-256-GCM.

    Returns: nonce (12 bytes) + ciphertext + tag (16 bytes)
    """
    key = _get_key(key_hex)
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(key)
    try:
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e
    return nonce + ciphertext


def decrypt(ciphertext_with_nonce: bytes, key_hex: str) -> str:
    """
    Decrypt AES-256-GCM encrypted data.

    Expects: nonce (12 bytes) + ciphertext + tag (16 bytes)
    """
    key = _get_key(key_hex)
    if len(ciphertext_with_nonce) < _NONCE_LENGTH + 16:
        raise EncryptionError("Ciphertext too short to contain nonce and tag")
    nonce = ciphertext_with_nonce[:_NONCE_LENGTH]
    ciphertext = ciphertext_with_nonce[_NONCE_LENGTH:]
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise EncryptionError(f"Decryption failed: {e}") from e
    return plaintext.decode("utf-8")
