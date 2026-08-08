from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_delivery import EmailDelivery
from app.models.enums import EmailDeliveryStatus, EmailKind


class EmailDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        lead_id: uuid.UUID,
        kind: EmailKind,
        to_address: str,
        subject: str,
    ) -> EmailDelivery:
        """Stage an outbox row.

        Not committed here on purpose: the caller commits it in the same
        transaction as the lead itself.
        """
        delivery = EmailDelivery(
            lead_id=lead_id,
            kind=kind,
            to_address=to_address,
            subject=subject,
            status=EmailDeliveryStatus.PENDING,
        )
        self._session.add(delivery)
        return delivery

    async def get_by_id(self, delivery_id: uuid.UUID) -> EmailDelivery | None:
        return await self._session.get(EmailDelivery, delivery_id)

    async def list_for_lead(self, lead_id: uuid.UUID) -> list[EmailDelivery]:
        stmt = (
            select(EmailDelivery)
            .where(EmailDelivery.lead_id == lead_id)
            .order_by(EmailDelivery.created_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def mark_sent(
        self, delivery: EmailDelivery, *, provider_message_id: str | None
    ) -> None:
        delivery.status = EmailDeliveryStatus.SENT
        delivery.attempts += 1
        delivery.provider_message_id = provider_message_id
        delivery.sent_at = datetime.now(UTC)
        delivery.last_error = None
        await self._session.flush()

    async def mark_failed(self, delivery: EmailDelivery, *, error: str) -> None:
        delivery.status = EmailDeliveryStatus.FAILED
        delivery.attempts += 1
        # Bound the stored error: provider messages can be enormous.
        delivery.last_error = error[:2000]
        await self._session.flush()
