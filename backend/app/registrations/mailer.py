"""SMTP delivery for registration verification codes."""

import asyncio
import logging
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from smtplib import SMTP, SMTPException, SMTPRecipientsRefused, SMTP_SSL

from app.registrations.settings import RegistrationSettings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised without including recipient, message body, or OTP in logs."""


class RegistrationMailer:
    def __init__(self, settings: RegistrationSettings) -> None:
        self.settings = settings

    async def send_otp(self, recipient: str, first_name: str, otp: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Your Local AI verification code"
        message["From"] = formataddr(
            (self.settings.smtp_from_name, self.settings.smtp_from_email)
        )
        message["To"] = recipient
        name = escape(first_name)
        message.set_content(
            f"Hello {first_name},\n\nYour Local AI Platform verification code is {otp}. "
            "It expires in five minutes. Do not share this code with anyone."
        )
        message.add_alternative(f"""\
<!doctype html>
<html lang="en"><body style="margin:0;padding:32px;background:#f3f5f1;font-family:Arial,sans-serif;color:#26372e">
  <table role="presentation" style="max-width:560px;margin:auto;background:#fff;border:1px solid #e1e7df;border-radius:14px;padding:32px;width:100%">
    <tr><td><div style="font-size:12px;letter-spacing:2px;color:#52705d;font-weight:bold">LOCAL AI PLATFORM</div>
      <h1 style="font-size:24px;font-weight:500;margin:26px 0 10px">Verify your email</h1>
      <p style="font-size:15px;line-height:1.6">Hello {name}, use this code to complete your account registration.</p>
      <div style="margin:24px 0;padding:18px;background:#f3f6f2;border-radius:10px;text-align:center;font-size:34px;letter-spacing:12px;font-weight:bold;color:#294d3e">{otp}</div>
      <p style="font-size:14px;line-height:1.6">This code expires in <strong>five minutes</strong>.</p>
      <p style="font-size:13px;line-height:1.6;color:#6c756e">For your security, never share this code. If you did not request an account, you can ignore this email.</p>
    </td></tr>
  </table>
</body></html>""", subtype="html")

        try:
            await asyncio.to_thread(self._send, message)
        except (OSError, SMTPException, TimeoutError, EmailDeliveryError) as error:
            # Never include exception text here: some SMTP servers include message
            # contents or authentication details in their response strings.
            logger.warning("Registration OTP email delivery failed (%s).", type(error).__name__)
            raise EmailDeliveryError("Registration email could not be delivered.") from None
        logger.info("Registration OTP email accepted by SMTP server.")

    def _send(self, message: EmailMessage) -> None:
        smtp_type = SMTP_SSL if self.settings.smtp_use_ssl else SMTP
        client = smtp_type(self.settings.smtp_host, self.settings.smtp_port, timeout=10)
        try:
            if not self.settings.smtp_use_ssl:
                client.ehlo()
            if self.settings.smtp_use_tls:
                client.starttls()
                client.ehlo()
            if self.settings.smtp_username and self.settings.smtp_password:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            refused = client.send_message(message)
            if refused:
                raise SMTPRecipientsRefused(refused)
        finally:
            try:
                client.quit()
            except (OSError, SMTPException):
                client.close()
