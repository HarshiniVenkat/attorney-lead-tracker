from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)

# Any bcrypt hash of the right shape works here; the value is never matched.
_DUMMY_HASH = "$2b$12$" + "." * 53


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def authenticate(self, *, email: str, password: str) -> User:
        user = await self._users.get_by_email(email)

        if user is None:
            # Hash anyway so a missing account and a wrong password take the
            # same time; otherwise response latency enumerates valid emails.
            verify_password(password, _DUMMY_HASH)
            raise UnauthorizedError("Incorrect email or password.")

        if not verify_password(password, user.hashed_password):
            logger.warning("login_failed", extra={"email": email, "reason": "bad_password"})
            raise UnauthorizedError("Incorrect email or password.")

        if not user.is_active:
            # Deliberately distinct from bad credentials: a deactivated
            # attorney knows their password is fine and needs to contact an
            # admin, not keep retrying.
            logger.warning("login_failed", extra={"email": email, "reason": "inactive"})
            raise UnauthorizedError(
                "This account has been deactivated.", code="account_inactive"
            )

        logger.info("login_succeeded", extra={"user_id": str(user.id)})
        return user

    async def login(self, *, email: str, password: str) -> tuple[str, int, User]:
        user = await self.authenticate(email=email, password=password)
        token, expires_in = create_access_token(user.id, email=user.email)
        return token, expires_in, user

    async def get_active_user(self, user_id: uuid.UUID) -> User:
        """Resolve the subject of a valid token, re-checking it is still usable.

        A token stays cryptographically valid until it expires, so
        deactivation only takes effect if it is checked on every request.
        """
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("Account no longer exists.")
        if not user.is_active:
            raise UnauthorizedError(
                "This account has been deactivated.", code="account_inactive"
            )
        return user

    async def create_user(
        self, *, email: str, password: str, full_name: str
    ) -> User:
        return await self._users.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
