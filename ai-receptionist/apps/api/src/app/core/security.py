"""Security primitives: webhook signature verification and credential
encryption.

- Voice-vendor webhooks are HMAC-signed; every inbound webhook must pass
  `verify_webhook_signature` before any processing (rejecting unsigned or
  tampered payloads at the edge).
- Per-tenant integration credentials (Google/HubSpot OAuth tokens) are
  encrypted at rest with Fernet (AES-128-CBC + HMAC); the key lives only in
  the environment, never in the database.
"""

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AppError, WebhookSignatureError


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> None:
    """Constant-time HMAC-SHA256 verification. Raises on mismatch."""
    if not secret:
        raise WebhookSignatureError("webhook secret not configured")
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise WebhookSignatureError("signature mismatch")


class CredentialCipher:
    """Encrypts/decrypts per-tenant integration credentials at rest."""

    def __init__(self, key: str) -> None:
        if not key:
            raise AppError("CREDENTIALS_ENCRYPTION_KEY is not configured")
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise AppError("credential decryption failed — key rotated?") from exc
