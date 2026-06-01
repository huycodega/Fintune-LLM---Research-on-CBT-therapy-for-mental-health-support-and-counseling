"""
AES-256-GCM field-level encryption for PHI (PostgreSQL BYTEA columns).

Format on disk:  nonce(12) || ciphertext+tag

This is the simplest construction that gives confidentiality + integrity.
The key comes from settings.phi_key() — set PHI_AES_KEY_B64 in env (or
the value auto-generated at first boot for a fresh dev env).

Usage:
    enc = encrypt_phi("She lives alone with multiple pets")
    plain = decrypt_phi(enc).decode()
"""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def encrypt_phi(plaintext: str | bytes) -> bytes:
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    nonce = os.urandom(12)
    ct = AESGCM(settings.phi_key()).encrypt(nonce, plaintext, None)
    return nonce + ct


def decrypt_phi(blob: bytes | None) -> bytes:
    if not blob:
        return b""
    if len(blob) < 13:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(settings.phi_key()).decrypt(nonce, ct, None)


def decrypt_str(blob: bytes | None) -> str:
    return decrypt_phi(blob).decode("utf-8") if blob else ""
