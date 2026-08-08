from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        # Emails are stored as entered but matched case-insensitively, so
        # "Attorney@alma.test" and "attorney@alma.test" are the same account.
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(
        self, *, email: str, hashed_password: str, full_name: str, is_active: bool = True
    ) -> User:
        user = User(
            email=email.strip().lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        return user
