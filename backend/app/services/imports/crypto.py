from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _key() -> bytes:
    configured = settings.external_tokens_key
    if configured:
        raw = base64.b64decode(configured)
        if len(raw) != 32:
            msg = "EXTERNAL_TOKENS_KEY must be 32 bytes, base64-encoded"
            raise ValueError(msg)
        return raw
    return hashlib.sha256(settings.app_secret_key.encode()).digest()


def encrypt_token(value: str) -> bytes:
    nonce = os.urandom(12)
    sealed = AESGCM(_key()).encrypt(nonce, value.encode(), None)
    return nonce + sealed


def decrypt_token(payload: bytes) -> str:
    nonce, sealed = payload[:12], payload[12:]
    return AESGCM(_key()).decrypt(nonce, sealed, None).decode()
