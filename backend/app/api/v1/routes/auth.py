from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange attorney credentials for an access token",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Bad credentials or a deactivated account.",
        }
    },
)
async def login(payload: LoginRequest, auth_service: AuthServiceDep) -> TokenResponse:
    token, expires_in, _ = await auth_service.login(
        email=payload.email, password=payload.password
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the authenticated attorney",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def read_current_user(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
