"""Email port.

Adapters are selected by config, so tests capture messages in memory and the
compose stack routes everything to MailHog without touching calling code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str
    reply_to: str | None = None


@dataclass(slots=True, frozen=True)
class SendResult:
    message_id: str | None


class EmailSendError(Exception):
    """Raised when an adapter cannot hand the message to its provider."""


class EmailBackend(ABC):
    @abstractmethod
    async def send(self, message: EmailMessage) -> SendResult:
        """Deliver `message`, or raise EmailSendError."""
