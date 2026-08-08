"""Authentication and access control."""

from __future__ import annotations

from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User


async def test_login_returns_a_token(client: AsyncClient, attorney: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "attorney@example.com", "password": "changeme123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]


async def test_login_is_case_insensitive_on_email(client: AsyncClient, attorney: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ATTORNEY@Example.COM", "password": "changeme123"},
    )
    assert response.status_code == 200


async def test_wrong_password_is_rejected(client: AsyncClient, attorney: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "attorney@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_unknown_account_gives_the_same_message(client: AsyncClient, attorney: User):
    """Login must not reveal whether an address has an account."""
    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "changeme123"},
    )
    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "attorney@example.com", "password": "wrong"},
    )

    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json()["error"]["message"] == wrong_password.json()["error"]["message"]


async def test_deactivated_account_cannot_log_in(
    client: AsyncClient, attorney: User, session
):
    attorney.is_active = False
    session.add(attorney)
    await session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "attorney@example.com", "password": "changeme123"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "account_inactive"


async def test_deactivation_invalidates_an_existing_token(
    client: AsyncClient, attorney: User, session, auth_headers: dict[str, str]
):
    """A still-valid JWT must stop working the moment the account is disabled.

    This is the reason `is_active` is re-checked on every request instead of
    being trusted from the token claims.
    """
    before = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert before.status_code == 200

    attorney.is_active = False
    session.add(attorney)
    await session.commit()

    after = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "account_inactive"


async def test_me_returns_the_current_attorney(
    client: AsyncClient, attorney: User, auth_headers: dict[str, str]
):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "attorney@example.com"
    assert body["full_name"] == "Alma Attorney"
    assert body["is_active"] is True
    assert "hashed_password" not in body


async def test_missing_token_is_rejected(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_garbage_token_is_rejected(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401


async def test_token_for_a_deleted_account_is_rejected(client: AsyncClient):
    """A well-signed token whose subject no longer exists must not authenticate."""
    import uuid

    token, _ = create_access_token(uuid.uuid4(), email="ghost@example.com")
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
