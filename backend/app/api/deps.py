"""FastAPI dependencies: DB session, current user, service construction."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import SessionFactory
from app.models.user import User
from app.services.auth import AuthService
from app.services.lead import LeadService

# auto_error=False so a missing header raises our envelope, not FastAPI's.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """One transaction per request: commit on success, roll back on error."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Authentication required.")

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc

    # Re-checked against the DB on every request so deactivating an attorney
    # takes effect immediately rather than at token expiry.
    return await AuthService(session).get_active_user(user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_lead_service(session: DbSession) -> LeadService:
    return LeadService(session)


LeadServiceDep = Annotated[LeadService, Depends(get_lead_service)]


def get_auth_service(session: DbSession) -> AuthService:
    return AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


class PaginationParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="1-indexed page number.")] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.page = page
        self.page_size = page_size


Pagination = Annotated[PaginationParams, Depends()]
