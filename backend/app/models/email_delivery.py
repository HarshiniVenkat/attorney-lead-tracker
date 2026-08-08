from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EmailDeliveryStatus, EmailKind

if TYPE_CHECKING:
    from app.models.lead import Lead


class EmailDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Transactional outbox row: one per email the system owes.

    Written in the same transaction as the lead it belongs to, so a lead can
    never exist without a durable record of the emails owed on it. Dispatch is
    attempted once immediately after commit; a failure is recorded here rather
    than lost, which makes "did the attorney actually get notified?" a query
    instead of a guess.
    """

    __tablename__ = "email_deliveries"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[EmailKind] = mapped_column(
        SAEnum(EmailKind, name="email_kind", native_enum=True, validate_strings=True),
        nullable=False,
    )
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)

    status: Mapped[EmailDeliveryStatus] = mapped_column(
        SAEnum(
            EmailDeliveryStatus,
            name="email_delivery_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=EmailDeliveryStatus.PENDING,
        server_default=EmailDeliveryStatus.PENDING.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Populated but unread today. Retry is deliberately out of scope for v1;
    # these columns exist so the retry worker is a pure addition, not a
    # migration. See SYSTEM_OVERVIEW.md ("What we deliberately did not build").
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    lead: Mapped[Lead] = relationship(back_populates="email_deliveries")

    def __repr__(self) -> str:
        return f"<EmailDelivery {self.kind} {self.status}>"
