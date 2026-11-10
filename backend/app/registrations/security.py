"""Encryption and keyed OTP hashing for pending registration records."""

import hashlib
import hmac
import os
import secrets
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class RegistrationCrypto:
    def __init__(self, key_dir: str | Path) -> None:
        self.key_dir = Path(key_dir)
        self._master_key: bytes | None = None

    def _key(self) -> bytes:
        if self._master_key is not None:
            return self._master_key

        self.key_dir.mkdir(parents=True, exist_ok=True)
        path = self.key_dir / "registration.key"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            key = path.read_bytes()
        else:
            key = secrets.token_bytes(32)
            with os.fdopen(descriptor, "wb") as key_file:
                key_file.write(key)
                key_file.flush()
                os.fsync(key_file.fileno())
        if len(key) != 32:
            raise RuntimeError("Registration encryption key is missing or invalid.")
        self._master_key = key
        return key

    def _derive(self, purpose: bytes) -> bytes:
        return hmac.new(self._key(), b"local-ai-registration-v1:" + purpose, hashlib.sha256).digest()

    def encrypt_password(self, password: str, registration_id: UUID) -> tuple[bytes, bytes]:
        nonce = secrets.token_bytes(12)
        encrypted = AESGCM(self._derive(b"password-encryption")).encrypt(
            nonce, password.encode("utf-8"), registration_id.bytes
        )
        return nonce, encrypted

    def decrypt_password(self, nonce: bytes, ciphertext: bytes, registration_id: UUID) -> str:
        plaintext = AESGCM(self._derive(b"password-encryption")).decrypt(
            nonce, ciphertext, registration_id.bytes
        )
        return plaintext.decode("utf-8")

    def otp_salt(self) -> bytes:
        return secrets.token_bytes(16)

    def otp_digest(self, registration_id: UUID, salt: bytes, otp: str) -> bytes:
        payload = registration_id.bytes + salt + otp.encode("ascii")
        return hmac.new(self._derive(b"otp-hmac"), payload, hashlib.sha256).digest()

    def check_otp(self, registration_id: UUID, salt: bytes, otp: str, expected: bytes) -> bool:
        return hmac.compare_digest(self.otp_digest(registration_id, salt, otp), expected)

    def rate_limit_key(self, client_ip: str, action: str) -> str:
        digest = hmac.new(
            self._derive(b"rate-limit-hmac"),
            f"{action}:{client_ip}".encode("utf-8"),
            hashlib.sha256,
        )
        return digest.hexdigest()
