"""Unit tests for SMTP delivery without a live provider or credentials."""

import logging
from collections.abc import Callable
from smtplib import SMTPAuthenticationError
from unittest.mock import MagicMock, patch

import pytest

from app.registrations.mailer import EmailDeliveryError, RegistrationMailer
from app.registrations.settings import RegistrationSettings


@pytest.fixture(autouse=True)
def run_mocked_smtp_without_threads(monkeypatch: pytest.MonkeyPatch):
    async def run_inline(function: Callable, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr("app.registrations.mailer.asyncio.to_thread", run_inline)


def settings(**overrides) -> RegistrationSettings:
    values = {
        "APP_DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
        "EMAIL_PROVIDER": "smtp",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "smtp-user",
        "SMTP_PASSWORD": "smtp-password",
        "SMTP_USE_TLS": True,
        "SMTP_FROM_EMAIL": "no-reply@example.test",
        "SMTP_FROM_NAME": "Local AI",
    }
    values.update(overrides)
    return RegistrationSettings(**values)


@pytest.mark.anyio
async def test_smtp_uses_starttls_auth_and_sender_name():
    client = MagicMock()
    client.send_message.return_value = {}
    with patch("app.registrations.mailer.SMTP", return_value=client) as smtp:
        await RegistrationMailer(settings()).send_otp("user@example.test", "A User", "0234")

    smtp.assert_called_once_with("smtp.example.test", 587, timeout=10)
    client.starttls.assert_called_once_with()
    client.login.assert_called_once_with("smtp-user", "smtp-password")
    delivered = client.send_message.call_args.args[0]
    assert delivered["From"] == "Local AI <no-reply@example.test>"
    assert "0234" in delivered.get_body(preferencelist=("plain",)).get_content()
    assert "0234" in delivered.get_body(preferencelist=("html",)).get_content()
    client.quit.assert_called_once_with()


@pytest.mark.anyio
async def test_smtp_recipient_rejection_is_delivery_failure(caplog: pytest.LogCaptureFixture):
    client = MagicMock()
    client.send_message.return_value = {"user@example.test": (550, b"OTP 0234 refused")}
    with patch("app.registrations.mailer.SMTP", return_value=client):
        with caplog.at_level(logging.WARNING):
            with pytest.raises(EmailDeliveryError, match="could not be delivered"):
                await RegistrationMailer(settings()).send_otp(
                    "user@example.test", "A User", "0234"
                )
    assert "0234" not in caplog.text
    assert "user@example.test" not in caplog.text
    assert "smtp-password" not in caplog.text


@pytest.mark.anyio
async def test_smtp_connection_and_authentication_failures_are_sanitized(caplog):
    client = MagicMock()
    client.login.side_effect = SMTPAuthenticationError(535, b"secret credentials")
    for smtp_patch in (
        patch("app.registrations.mailer.SMTP", side_effect=OSError("secret host details")),
        patch("app.registrations.mailer.SMTP", return_value=client),
        patch("app.registrations.mailer.SMTP", return_value=MagicMock(
            send_message=MagicMock(return_value={"user@example.test": (550, b"secret")})
        )),
    ):
        with smtp_patch, caplog.at_level(logging.WARNING):
            with pytest.raises(EmailDeliveryError):
                await RegistrationMailer(settings()).send_otp(
                    "user@example.test", "A User", "9876"
                )
    assert "9876" not in caplog.text
    assert "secret" not in caplog.text
    assert "smtp-password" not in caplog.text


def test_invalid_smtp_auth_pair_is_rejected():
    with pytest.raises(ValueError, match="both SMTP_USERNAME and SMTP_PASSWORD"):
        settings(SMTP_PASSWORD="")
