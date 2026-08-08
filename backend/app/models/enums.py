from __future__ import annotations

from enum import StrEnum


class LeadState(StrEnum):
    PENDING = "PENDING"
    REACHED_OUT = "REACHED_OUT"


class EmailKind(StrEnum):
    PROSPECT_CONFIRMATION = "PROSPECT_CONFIRMATION"
    ATTORNEY_NOTIFICATION = "ATTORNEY_NOTIFICATION"


class EmailDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
