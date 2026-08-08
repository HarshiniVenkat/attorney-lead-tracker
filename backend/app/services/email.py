"""Email composition and outbox dispatch.

Two responsibilities, deliberately split:

  `enqueue_lead_emails` stages outbox rows inside the caller's transaction.
  `dispatch_pending_for_lead` attempts delivery afterwards, out of band.

Nothing here is allowed to raise into the request path — a mail failure is
recorded on the outbox row, never surfaced to the prospect.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import session_scope
from app.integrations.email.base import EmailBackend, EmailMessage, EmailSendError
from app.integrations.email.factory import get_email_backend
from app.models.email_delivery import EmailDelivery
from app.models.enums import EmailDeliveryStatus, EmailKind
from app.models.lead import Lead
from app.repositories.email_delivery import EmailDeliveryRepository

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

# StrictUndefined turns a typo'd template variable into a loud error at render
# time instead of a silently blank line in a customer-facing email.
_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(template_name: str, context: dict) -> str:
    return _jinja_env.get_template(template_name).render(**context)


def _lead_context(lead: Lead) -> dict:
    return {
        "brand_name": settings.email_from_name,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.full_name,
        "email": lead.email,
        "resume_filename": lead.resume_filename,
        "submitted_at": lead.created_at.strftime("%d %b %Y at %H:%M UTC")
        if lead.created_at
        else datetime.now(UTC).strftime("%d %b %Y at %H:%M UTC"),
        "lead_url": f"{settings.internal_app_base_url.rstrip('/')}/admin/leads/{lead.id}",
    }


def _subject_for(kind: EmailKind, lead: Lead) -> str:
    if kind is EmailKind.PROSPECT_CONFIRMATION:
        return f"We received your application, {lead.first_name}"
    return f"New lead: {lead.full_name}"


def _template_stem(kind: EmailKind) -> str:
    return (
        "prospect_confirmation"
        if kind is EmailKind.PROSPECT_CONFIRMATION
        else "attorney_notification"
    )


def build_message(kind: EmailKind, lead: Lead, *, to_address: str) -> EmailMessage:
    context = _lead_context(lead) | {"subject": _subject_for(kind, lead)}
    stem = _template_stem(kind)
    return EmailMessage(
        to=to_address,
        subject=context["subject"],
        html_body=_render(f"{stem}.html", context),
        text_body=_render(f"{stem}.txt", context),
        # Lets the attorney hit reply and land in the prospect's inbox.
        reply_to=lead.email if kind is EmailKind.ATTORNEY_NOTIFICATION else None,
    )


class EmailService:
    def __init__(self, session: AsyncSession, backend: EmailBackend | None = None) -> None:
        self._session = session
        self._deliveries = EmailDeliveryRepository(session)
        self._backend = backend or get_email_backend()

    def enqueue_lead_emails(self, lead: Lead) -> list[EmailDelivery]:
        """Stage both outbox rows. Committed by the caller alongside the lead."""
        recipients = (
            (EmailKind.PROSPECT_CONFIRMATION, lead.email),
            (EmailKind.ATTORNEY_NOTIFICATION, settings.attorney_notification_email),
        )
        return [
            self._deliveries.enqueue(
                lead_id=lead.id,
                kind=kind,
                to_address=to_address,
                subject=_subject_for(kind, lead),
            )
            for kind, to_address in recipients
        ]

    async def _attempt(self, delivery: EmailDelivery, lead: Lead) -> bool:
        try:
            message = build_message(delivery.kind, lead, to_address=delivery.to_address)
            result = await self._backend.send(message)
        except EmailSendError as exc:
            await self._deliveries.mark_failed(delivery, error=str(exc))
            logger.warning(
                "email_delivery_failed",
                extra={
                    "delivery_id": str(delivery.id),
                    "lead_id": str(lead.id),
                    "kind": delivery.kind.value,
                    "error": str(exc),
                },
            )
            return False
        except Exception as exc:
            # A template bug or bad config must not escape into the caller.
            await self._deliveries.mark_failed(delivery, error=f"{type(exc).__name__}: {exc}")
            logger.exception(
                "email_delivery_error",
                extra={"delivery_id": str(delivery.id), "lead_id": str(lead.id)},
            )
            return False

        await self._deliveries.mark_sent(delivery, provider_message_id=result.message_id)
        logger.info(
            "email_delivery_sent",
            extra={
                "delivery_id": str(delivery.id),
                "lead_id": str(lead.id),
                "kind": delivery.kind.value,
            },
        )
        return True

    async def dispatch_for_lead(self, lead_id: uuid.UUID) -> int:
        """Attempt every still-pending delivery for a lead. Returns sent count."""
        from app.repositories.lead import LeadRepository

        lead = await LeadRepository(self._session).get_by_id(lead_id)
        if lead is None:
            logger.warning("email_dispatch_lead_missing", extra={"lead_id": str(lead_id)})
            return 0

        pending = [
            delivery
            for delivery in await self._deliveries.list_for_lead(lead_id)
            if delivery.status is not EmailDeliveryStatus.SENT
        ]

        sent = 0
        for delivery in pending:
            if await self._attempt(delivery, lead):
                sent += 1
        return sent


async def dispatch_lead_emails_task(lead_id: uuid.UUID) -> None:
    """Background entrypoint: owns its own session, swallows every error.

    Runs after the request's transaction has committed, so it opens a fresh
    session rather than borrowing the request-scoped one.
    """
    try:
        async with session_scope() as session:
            await EmailService(session).dispatch_for_lead(lead_id)
    except Exception:
        # The outbox rows stay PENDING/FAILED and remain visible in the admin
        # UI, which is the whole point of persisting them.
        logger.exception("email_dispatch_task_failed", extra={"lead_id": str(lead_id)})
