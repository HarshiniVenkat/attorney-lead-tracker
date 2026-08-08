from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    # Plain str, not EmailStr: this is matched against an existing account
    # rather than accepted as new data. Strict address validation here would
    # lock out any account whose address the validator dislikes (internal
    # domains, special-use TLDs) without making anything safer.
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds.")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Response models echo stored data; re-validating it would turn a legacy
    # or unusual address into a 500 instead of a rendered row.
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
