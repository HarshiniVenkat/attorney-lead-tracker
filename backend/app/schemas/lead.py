from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import EmailDeliveryStatus, EmailKind, LeadState


class LeadCreateForm(BaseModel):
    """Text fields of the public multipart submission.

    The resume arrives as an UploadFile alongside this and is validated
    separately by app.validators.upload.
    """

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("first_name", "last_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("This field is required.")
        return value


class LeadCreatedResponse(BaseModel):
    """Deliberately minimal: the public endpoint echoes nothing back."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state: LeadState
    created_at: datetime


# Response models below use plain `str` for addresses on purpose. Validation
# belongs on the way in (LeadCreateForm above); re-validating stored data on
# the way out would turn an unusual-but-real address into a 500.
class ActorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str


class LeadListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    state: LeadState
    created_at: datetime
    updated_at: datetime
    reached_out_at: datetime | None = None
    reached_out_by: ActorSummary | None = None


class EmailDeliverySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EmailKind
    to_address: str
    status: EmailDeliveryStatus
    attempts: int
    last_error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


class LeadStateEventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_state: LeadState | None
    to_state: LeadState
    created_at: datetime
    actor: ActorSummary | None = None


class LeadDetail(LeadListItem):
    resume_filename: str
    resume_content_type: str
    resume_size_bytes: int
    state_events: list[LeadStateEventSummary] = Field(default_factory=list)
    email_deliveries: list[EmailDeliverySummary] = Field(default_factory=list)


class LeadUpdateRequest(BaseModel):
    """The only mutation the internal UI performs."""

    state: LeadState
