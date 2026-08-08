"""SMTP adapter (MailHog locally, any relay in production)."""

from __future__ import annotations

import logging
import uuid
from email.message import EmailMessage as MIMEMessage
from email.utils import formataddr, make_msgid

import aiosmtplib

from app.core.config import settings
from app.integrations.email.base import (
    EmailBackend,
    EmailMessage,
    EmailSendError,
    SendResult,
)

logger = logging.getLogger(__name__)


class SMTPEmailBackend(EmailBackend):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        from_address: str,
        from_name: str,
        timeout_seconds: int = 10,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username or None
        self._password = password or None
        self._use_tls = use_tls
        self._from_address = from_address
        self._from_name = from_name
        self._timeout = timeout_seconds

    def _build_mime(self, message: EmailMessage) -> tuple[MIMEMessage, str]:
        mime = MIMEMessage()
        mime["From"] = formataddr((self._from_name, self._from_address))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        if message.reply_to:
            mime["Reply-To"] = message.reply_to

        message_id = make_msgid(domain=self._from_address.rpartition("@")[2] or None)
        mime["Message-ID"] = message_id

        # Plain text first, HTML second: clients render the last part they
        # understand, so the rich version wins where it is supported.
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        return mime, message_id

    async def send(self, message: EmailMessage) -> SendResult:
        mime, message_id = self._build_mime(message)
        try:
            await aiosmtplib.send(
                mime,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=self._use_tls or None,
                timeout=self._timeout,
            )
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
            raise EmailSendError(f"SMTP delivery failed: {exc}") from exc

        logger.info("email_sent", extra={"to": message.to, "message_id": message_id})
        return SendResult(message_id=message_id)


class ConsoleEmailBackend(EmailBackend):
    """Logs messages instead of sending. Used when no relay is available."""

    async def send(self, message: EmailMessage) -> SendResult:
        message_id = f"console-{uuid.uuid4()}"
        logger.info(
            "email_sent_console",
            extra={
                "to": message.to,
                "subject": message.subject,
                "message_id": message_id,
                "body": message.text_body,
            },
        )
        return SendResult(message_id=message_id)


def build_smtp_backend() -> SMTPEmailBackend:
    return SMTPEmailBackend(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        from_address=settings.email_from,
        from_name=settings.email_from_name,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
