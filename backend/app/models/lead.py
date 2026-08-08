from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import LeadState

if TYPE_CHECKING:
    from app.models.email_delivery import EmailDelivery
    from app.models.user import User


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A prospect submission from the public form."""

    __tablename__ = "leads"
    __table_args__ = (
        # Serves the default admin view: filter by state, newest first.
        Index("ix_leads_state_created_at", "state", "created_at"),
        Index("ix_leads_email", "email"),
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)

    # Storage key is generated server-side; the prospect's filename is kept
    # only to set Content-Disposition on download.
    resume_key: Mapped[str] = mapped_column(String(512), nullable=False)
    resume_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    resume_content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    resume_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    state: Mapped[LeadState] = mapped_column(
        SAEnum(LeadState, name="lead_state", native_enum=True, validate_strings=True),
        nullable=False,
        default=LeadState.PENDING,
        server_default=LeadState.PENDING.value,
    )

    reached_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reached_out_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reached_out_by: Mapped[User | None] = relationship(
        back_populates="reached_out_leads",
        foreign_keys=[reached_out_by_id],
        lazy="joined",
    )
    state_events: Mapped[list[LeadStateEvent]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadStateEvent.created_at",
    )
    email_deliveries: Mapped[list[EmailDelivery]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="EmailDelivery.created_at",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Lead {self.email} {self.state}>"


class LeadStateEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only record of every state transition on a lead."""

    __tablename__ = "lead_state_events"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_state: Mapped[LeadState | None] = mapped_column(
        SAEnum(LeadState, name="lead_state", native_enum=True, create_type=False),
        nullable=True,
    )
    to_state: Mapped[LeadState] = mapped_column(
        SAEnum(LeadState, name="lead_state", native_enum=True, create_type=False),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    lead: Mapped[Lead] = relationship(back_populates="state_events")
    actor: Mapped[User | None] = relationship(back_populates="state_events", lazy="joined")
