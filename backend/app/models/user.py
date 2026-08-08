from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead, LeadStateEvent


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An attorney with access to the internal UI."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Attorneys are retired by flipping this flag rather than deleting the row:
    # leads.reached_out_by_id and lead_state_events.actor_id point here, so a
    # delete would take the audit trail with it.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reached_out_leads: Mapped[list[Lead]] = relationship(
        back_populates="reached_out_by",
        foreign_keys="Lead.reached_out_by_id",
    )
    state_events: Mapped[list[LeadStateEvent]] = relationship(back_populates="actor")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
