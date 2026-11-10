import asyncio
import os
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.registrations.keycloak_admin import (
    DuplicateKeycloakAccount,
    KeycloakAdminUnavailable,
)
from app.registrations.security import RegistrationCrypto
from app.registrations.service import RegistrationService
from app.registrations.store import RegistrationStore
from app.schemas.registration import RegistrationRequest

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


class FakeMailer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []
        self.fail = False

    async def send_otp(self, email: str, first_name: str, otp: str) -> None:
        if self.fail:
            from app.registrations.mailer import EmailDeliveryError

            raise EmailDeliveryError("mock mail failure")
        self.messages.append((email, first_name, otp))


class FakeKeycloak:
    def __init__(self) -> None:
        self.accounts: dict[str, dict[str, str]] = {}
        self.fail = False
        self.fail_after_create = False
        self.calls = 0
        self.delay = 0

    async def account_exists(self, username: str, email: str) -> bool:
        return any(
            account["username"].casefold() == username.casefold()
            or account["email"].casefold() == email.casefold()
            for account in self.accounts.values()
        )

    async def provision_verified_user(self, account: dict[str, str], password: str) -> None:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        key = account["username"].casefold()
        if self.fail:
            raise KeycloakAdminUnavailable("mock Keycloak failure")
        if key in self.accounts:
            if self.accounts[key]["email"].casefold() != account["email"].casefold():
                raise DuplicateKeycloakAccount()
        self.accounts[key] = {**account, "password": password, "email_verified": "true"}
        if self.fail_after_create:
            self.fail_after_create = False
            raise KeycloakAdminUnavailable("mock response lost after create")


@dataclass
class Harness:
    store: RegistrationStore
    crypto: RegistrationCrypto
    mailer: FakeMailer
    keycloak: FakeKeycloak
    service: RegistrationService
    registration_ids: list[UUID] = field(default_factory=list)


@pytest.fixture
async def harness(tmp_path):
    database_url = os.getenv("TEST_APP_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_APP_DATABASE_URL to run persistent PostgreSQL registration tests.")
    store = RegistrationStore(database_url)
    await store.initialize()
    crypto = RegistrationCrypto(tmp_path)
    mailer = FakeMailer()
    keycloak = FakeKeycloak()
    service = RegistrationService(store, crypto, mailer, keycloak)
    result = Harness(store, crypto, mailer, keycloak, service)
    yield result
    for registration_id in result.registration_ids:
        await store.delete_pending(registration_id)
    await store.close()


def registration_data(suffix: str) -> RegistrationRequest:
    return RegistrationRequest(
        username=f"otp-test-{suffix}",
        email=f"otp-test-{suffix}@example.com",
        first_name="OTP",
        last_name="Test",
        password="a-very-secure-test-password",
        confirm_password="a-very-secure-test-password",
    )


async def register(harness: Harness, suffix: str, ip: str | None = None):
    response = await harness.service.register(
        registration_data(suffix), ip or f"test-{uuid4()}"
    )
    registration_id = UUID(str(response["registration_id"]))
    harness.registration_ids.append(registration_id)
    return registration_id, harness.mailer.messages[-1][2]


async def expect_http(status_code: int, operation) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await operation
    assert raised.value.status_code == status_code
    return raised.value


async def test_registration_sends_four_digit_otp_and_stores_only_hash(harness: Harness):
    registration_id, otp = await register(harness, str(uuid4()).replace("-", ""))
    assert len(otp) == 4 and otp.isdigit()
    assert harness.mailer.messages[-1][0].endswith("@example.com")
    async with harness.store.engine.connect() as connection:
        row = (await connection.execute(text(
            "SELECT otp_hash, password_ciphertext FROM pending_registrations WHERE id = :id"
        ), {"id": registration_id})).mappings().one()
    assert row["otp_hash"] == harness.crypto.otp_digest(
        registration_id,
        await _otp_salt(harness, registration_id),
        otp,
    )
    assert otp.encode() not in row["otp_hash"]
    assert b"a-very-secure-test-password" not in row["password_ciphertext"]
    assert not harness.keycloak.accounts


async def _otp_salt(harness: Harness, registration_id: UUID) -> bytes:
    async with harness.store.engine.connect() as connection:
        return (await connection.execute(text(
            "SELECT otp_salt FROM pending_registrations WHERE id = :id"
        ), {"id": registration_id})).scalar_one()


async def test_duplicate_pending_username_or_email_is_rejected(harness: Harness):
    suffix = str(uuid4()).replace("-", "")
    await register(harness, suffix)
    duplicate_username = registration_data(suffix + "x")
    duplicate_username.username = f"otp-test-{suffix}"
    await expect_http(409, harness.service.register(duplicate_username, f"ip-{uuid4()}"))

    duplicate_email = registration_data(suffix + "y")
    duplicate_email.email = f"otp-test-{suffix}@example.com"
    await expect_http(409, harness.service.register(duplicate_email, f"ip-{uuid4()}"))


async def test_correct_code_activates_user_once_and_prevents_reuse(harness: Harness):
    registration_id, otp = await register(harness, str(uuid4()).replace("-", ""))
    result = await harness.service.verify(registration_id, otp, f"ip-{uuid4()}")
    assert result["status"] == "verified"
    assert harness.keycloak.accounts
    account = next(iter(harness.keycloak.accounts.values()))
    assert account["email_verified"] == "true"
    assert account["password"] == "a-very-secure-test-password"
    await expect_http(404, harness.service.verify(registration_id, otp, f"ip-{uuid4()}"))


async def test_incorrect_code_locks_after_five_attempts(harness: Harness):
    registration_id, _ = await register(harness, str(uuid4()).replace("-", ""))
    ip = f"ip-{uuid4()}"
    for _ in range(4):
        await expect_http(400, harness.service.verify(registration_id, "9999", ip))
    await expect_http(429, harness.service.verify(registration_id, "9999", ip))
    assert not harness.keycloak.accounts


async def test_expired_code_is_rejected(harness: Harness):
    registration_id, otp = await register(harness, str(uuid4()).replace("-", ""))
    async with harness.store.engine.begin() as connection:
        await connection.execute(text(
            "UPDATE pending_registrations SET expires_at = NOW() - INTERVAL '1 second' WHERE id = :id"
        ), {"id": registration_id})
    await expect_http(410, harness.service.verify(registration_id, otp, f"ip-{uuid4()}"))
    assert not harness.keycloak.accounts


async def test_resend_cooldown_and_old_code_replacement(harness: Harness):
    registration_id, original = await register(harness, str(uuid4()).replace("-", ""))
    error = await expect_http(429, harness.service.resend(registration_id, f"ip-{uuid4()}"))
    assert error.headers["Retry-After"]
    async with harness.store.engine.begin() as connection:
        await connection.execute(text(
            "UPDATE pending_registrations SET resend_available_at = NOW() - INTERVAL '1 second' WHERE id = :id"
        ), {"id": registration_id})
    result = await harness.service.resend(registration_id, f"ip-{uuid4()}")
    assert result["resend_in_seconds"] == 60
    replacement = harness.mailer.messages[-1][2]
    assert len(replacement) == 4 and replacement.isdigit()
    await expect_http(400, harness.service.verify(registration_id, original, f"ip-{uuid4()}"))
    assert (await harness.service.verify(registration_id, replacement, f"ip-{uuid4()}"))["status"] == "verified"


async def test_resend_limit_is_enforced(harness: Harness):
    registration_id, _ = await register(harness, str(uuid4()).replace("-", ""))
    async with harness.store.engine.begin() as connection:
        await connection.execute(text(
            "UPDATE pending_registrations SET resend_count = 5, resend_available_at = NOW() - INTERVAL '1 second' WHERE id = :id"
        ), {"id": registration_id})
    await expect_http(429, harness.service.resend(registration_id, f"ip-{uuid4()}"))


async def test_registration_resend_and_verify_are_rate_limited(harness: Harness):
    registration_ip = f"register-{uuid4()}"
    for index in range(5):
        await register(harness, f"{uuid4().hex}", registration_ip)
    await expect_http(429, harness.service.register(registration_data(uuid4().hex), registration_ip))

    resend_ip = f"resend-{uuid4()}"
    for _ in range(10):
        await expect_http(404, harness.service.resend(uuid4(), resend_ip))
    await expect_http(429, harness.service.resend(uuid4(), resend_ip))

    verify_ip = f"verify-{uuid4()}"
    for _ in range(30):
        await expect_http(404, harness.service.verify(uuid4(), "0000", verify_ip))
    await expect_http(429, harness.service.verify(uuid4(), "0000", verify_ip))


async def test_keycloak_failure_keeps_code_retryable_and_is_idempotent(harness: Harness):
    registration_id, otp = await register(harness, str(uuid4()).replace("-", ""))
    harness.keycloak.fail_after_create = True
    await expect_http(503, harness.service.verify(registration_id, otp, f"ip-{uuid4()}"))
    assert await _pending_exists(harness, registration_id)
    result = await harness.service.verify(registration_id, otp, f"ip-{uuid4()}")
    assert result["status"] == "verified"
    assert len(harness.keycloak.accounts) == 1


async def _pending_exists(harness: Harness, registration_id: UUID) -> bool:
    async with harness.store.engine.connect() as connection:
        result = await connection.execute(text(
            "SELECT EXISTS(SELECT 1 FROM pending_registrations WHERE id = :id)"
        ), {"id": registration_id})
        return bool(result.scalar_one())


async def test_parallel_correct_codes_only_activate_once(harness: Harness):
    registration_id, otp = await register(harness, str(uuid4()).replace("-", ""))
    harness.keycloak.delay = 0.05
    results = await asyncio.gather(
        harness.service.verify(registration_id, otp, f"ip-{uuid4()}"),
        harness.service.verify(registration_id, otp, f"ip-{uuid4()}"),
        return_exceptions=True,
    )
    assert sum(isinstance(item, dict) and item["status"] == "verified" for item in results) == 1
    assert sum(isinstance(item, HTTPException) and item.status_code == 404 for item in results) == 1
    assert harness.keycloak.calls == 1


async def test_mail_delivery_failure_does_not_leave_pending_registration(harness: Harness):
    harness.mailer.fail = True
    data = registration_data(uuid4().hex)
    with pytest.raises(HTTPException) as raised:
        await harness.service.register(data, f"ip-{uuid4()}")
    assert raised.value.status_code == 503
    async with harness.store.engine.connect() as connection:
        exists = await connection.scalar(text(
            "SELECT EXISTS(SELECT 1 FROM pending_registrations WHERE email_key = :email)"
        ), {"email": str(data.email).casefold()})
    assert exists is False


async def test_mismatched_password_confirmation_is_invalid():
    with pytest.raises(ValueError, match="Passwords do not match"):
        RegistrationRequest(
            username="otp-test-user",
            email="otp-user@example.com",
            first_name="OTP",
            last_name="User",
            password="a-very-secure-test-password",
            confirm_password="different-secure-password",
        )
