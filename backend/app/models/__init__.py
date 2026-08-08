"""Model package.

Every model is imported here so that `Base.metadata` is fully populated by the
time Alembic autogenerate or `create_all` runs.
"""

from app.db.base import Base
from app.models.email_delivery import EmailDelivery
from app.models.enums import EmailDeliveryStatus, EmailKind, LeadState
from app.models.lead import Lead, LeadStateEvent
from app.models.user import User

__all__ = [
    "Base",
    "EmailDelivery",
    "EmailDeliveryStatus",
    "EmailKind",
    "Lead",
    "LeadState",
    "LeadStateEvent",
    "User",
]
