"""Durable pending-registration and IP rate-limit storage in PostgreSQL."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)


ProvisionUser = Callable[[dict[str, str], str], Awaitable[None]]
SendOtp = Callable[[str, str, str], Awaitable[None]]


class RegistrationStore:
    def __init__(self, database_url: str, *, engine: AsyncEngine | None = None) -> None:
        self.engine = engine or create_async_engine(database_url, pool_pre_ping=True)
        self._owns_engine = engine is None
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            async with self.engine.begin() as connection:
                await connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS pending_registrations (
                        id UUID PRIMARY KEY,
                        username TEXT NOT NULL,
                        username_key TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL,
                        email_key TEXT NOT NULL UNIQUE,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        password_nonce BYTEA NOT NULL,
                        password_ciphertext BYTEA NOT NULL,
                        otp_salt BYTEA NOT NULL,
                        otp_hash BYTEA NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        resend_available_at TIMESTAMPTZ NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        resend_count INTEGER NOT NULL DEFAULT 0,
                        state TEXT NOT NULL DEFAULT 'pending',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """))
                await connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS auth_rate_limits (
                        bucket_key CHAR(64) PRIMARY KEY,
                        window_started_at TIMESTAMPTZ NOT NULL,
                        request_count INTEGER NOT NULL
                    )
                """))
            self._initialized = True

    async def close(self) -> None:
        if self._owns_engine:
            await self.engine.dispose()

    async def delete_pending(self, registration_id: UUID) -> None:
        await self.initialize()
        async with self.engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM pending_registrations WHERE id = :id"),
                {"id": registration_id},
            )

    async def enforce_rate_limit(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> None:
        await self.initialize()
        statement = text("""
            INSERT INTO auth_rate_limits (bucket_key, window_started_at, request_count)
            VALUES (:bucket_key, NOW(), 1)
            ON CONFLICT (bucket_key) DO UPDATE SET
                request_count = CASE
                    WHEN auth_rate_limits.window_started_at <=
                        NOW() - (CAST(:window_seconds AS INTEGER) * INTERVAL '1 second')
                    THEN 1 ELSE auth_rate_limits.request_count + 1 END,
                window_started_at = CASE
                    WHEN auth_rate_limits.window_started_at <=
                        NOW() - (CAST(:window_seconds AS INTEGER) * INTERVAL '1 second')
                    THEN NOW() ELSE auth_rate_limits.window_started_at END
            RETURNING window_started_at, request_count
        """)
        async with self.engine.begin() as connection:
            await connection.execute(text("""
                DELETE FROM auth_rate_limits
                WHERE window_started_at < NOW() - INTERVAL '1 day'
            """))
            result = await connection.execute(
                statement,
                {"bucket_key": bucket_key, "window_seconds": window_seconds},
            )
            row = result.mappings().one()
        if row["request_count"] > limit:
            elapsed = datetime.now(timezone.utc) - row["window_started_at"]
            retry_after = window_seconds - int(elapsed.total_seconds())
            raise RateLimitExceeded(retry_after)

    async def create_pending(
        self,
        *,
        registration_id: UUID,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        password_nonce: bytes,
        password_ciphertext: bytes,
        otp_salt: bytes,
        otp_hash: bytes,
        otp_code: str,
        send_email: SendOtp,
    ) -> None:
        await self.initialize()
        async with self.engine.begin() as connection:
            await connection.execute(text("""
                DELETE FROM pending_registrations
                WHERE state IN ('pending', 'locked') AND expires_at <= NOW()
            """))
            await connection.execute(text("""
                INSERT INTO pending_registrations (
                    id, username, username_key, email, email_key, first_name, last_name,
                    password_nonce, password_ciphertext, otp_salt, otp_hash,
                    expires_at, resend_available_at
                ) VALUES (
                    :id, :username, :username_key, :email, :email_key, :first_name, :last_name,
                    :password_nonce, :password_ciphertext, :otp_salt, :otp_hash,
                    NOW() + INTERVAL '5 minutes', NOW() + INTERVAL '60 seconds'
                )
            """), {
                "id": registration_id,
                "username": username,
                "username_key": username.casefold(),
                "email": email,
                "email_key": email.casefold(),
                "first_name": first_name,
                "last_name": last_name,
                "password_nonce": password_nonce,
                "password_ciphertext": password_ciphertext,
                "otp_salt": otp_salt,
                "otp_hash": otp_hash,
            })
            await send_email(email, first_name, otp_code)

    async def resend(
        self,
        registration_id: UUID,
        *,
        otp_salt: bytes,
        otp_hash: bytes,
        otp_code: str,
        send_email: SendOtp,
    ) -> dict[str, Any]:
        await self.initialize()
        async with self.engine.begin() as connection:
            row = (await connection.execute(text("""
                SELECT * FROM pending_registrations WHERE id = :id FOR UPDATE
            """), {"id": registration_id})).mappings().first()
            if row is None:
                return {"status": "missing"}
            if row["state"] != "pending":
                return {"status": "locked"}
            now = datetime.now(timezone.utc)
            if row["expires_at"] <= now:
                await connection.execute(text("DELETE FROM pending_registrations WHERE id = :id"), {"id": registration_id})
                return {"status": "expired"}
            if row["resend_available_at"] > now:
                remaining = int((row["resend_available_at"] - now).total_seconds()) + 1
                return {"status": "cooldown", "retry_after": remaining}
            if row["resend_count"] >= 5:
                return {"status": "limit"}

            await send_email(row["email"], row["first_name"], otp_code)
            await connection.execute(text("""
                UPDATE pending_registrations
                SET otp_salt = :otp_salt, otp_hash = :otp_hash,
                    expires_at = NOW() + INTERVAL '5 minutes',
                    resend_available_at = NOW() + INTERVAL '60 seconds',
                    resend_count = resend_count + 1
                WHERE id = :id
            """), {"id": registration_id, "otp_salt": otp_salt, "otp_hash": otp_hash})
            return {"status": "sent", "expires_in_seconds": 300, "resend_in_seconds": 60}

    async def verify(
        self,
        registration_id: UUID,
        *,
        otp: str,
        crypto: Any,
        provision_user: ProvisionUser,
    ) -> dict[str, Any]:
        await self.initialize()
        async with self.engine.begin() as connection:
            row = (await connection.execute(text("""
                SELECT * FROM pending_registrations WHERE id = :id FOR UPDATE
            """), {"id": registration_id})).mappings().first()
            if row is None:
                return {"status": "missing"}
            if row["state"] != "pending":
                return {"status": "locked"}
            if row["expires_at"] <= datetime.now(timezone.utc):
                await connection.execute(text("DELETE FROM pending_registrations WHERE id = :id"), {"id": registration_id})
                return {"status": "expired"}
            if row["attempts"] >= 5:
                return {"status": "locked"}
            if not crypto.check_otp(registration_id, row["otp_salt"], otp, row["otp_hash"]):
                attempts = row["attempts"] + 1
                locked = attempts >= 5
                await connection.execute(text("""
                    UPDATE pending_registrations SET attempts = :attempts,
                        state = CASE WHEN :locked THEN 'locked' ELSE state END,
                        otp_hash = CASE WHEN :locked THEN :empty_hash ELSE otp_hash END
                    WHERE id = :id
                """), {
                    "id": registration_id,
                    "attempts": attempts,
                    "locked": locked,
                    "empty_hash": bytes(32),
                })
                return {"status": "locked" if locked else "incorrect", "attempts": attempts}

            password = crypto.decrypt_password(
                row["password_nonce"], row["password_ciphertext"], registration_id
            )
            account = {
                "username": row["username"],
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
            }
            await provision_user(account, password)
            await connection.execute(text("DELETE FROM pending_registrations WHERE id = :id"), {"id": registration_id})
            return {"status": "verified", "email": row["email"]}
