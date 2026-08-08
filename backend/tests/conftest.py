"""Test fixtures.

Integration tests run against a real Postgres (a throwaway `alma_test`
database) rather than SQLite, so the enum types, server defaults and
`ON DELETE` behaviour under test are the ones that actually ship.

Storage and email are swapped for in-memory fakes: those are the two ports the
app owns, and faking them keeps the suite fast, deterministic and offline.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import BinaryIO


# Redirect the app onto a dedicated test database *before* importing anything
# that reads settings, since Settings is resolved once at import time.
#
# These are unconditional assignments, not setdefault: the runtime environment
# already defines DATABASE_URL (docker-compose sets it), so setdefault would
# silently no-op and point the suite at the development database - whose tables
# the truncate fixture below would then wipe.
def _test_database_url() -> str:
    """Derive a `<name>_test` database from whatever DATABASE_URL is set."""
    configured = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://alma:alma@postgres:5432/alma"
    )
    base, _, name = configured.rpartition("/")
    name = name.split("?", 1)[0]
    return f"{base}/{name if name.endswith('_test') else f'{name}_test'}"


os.environ["DATABASE_URL"] = _test_database_url()
os.environ["STORAGE_BACKEND"] = "local"
os.environ["EMAIL_BACKEND"] = "console"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"
os.environ["ATTORNEY_NOTIFICATION_EMAIL"] = "attorney@example.com"
os.environ["MAX_RESUME_SIZE_BYTES"] = str(5 * 1024 * 1024)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.errors import NotFoundError  # noqa: E402
from app.core.rate_limit import enforce_public_submit_rate_limit  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionFactory, engine  # noqa: E402
from app.integrations.email.base import (  # noqa: E402
    EmailBackend,
    EmailMessage,
    EmailSendError,
    SendResult,
)
from app.integrations.storage.base import StorageBackend, StoredFile  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.user import User  # noqa: E402

TABLES = ["email_deliveries", "lead_state_events", "leads", "users"]

# Last line of defence. This suite truncates every table between tests, so
# pointing it at a non-test database destroys real data. Fail loudly at
# collection time rather than discovering it from an empty users table.
_ACTIVE_DATABASE = settings.database_url.rpartition("/")[2].split("?", 1)[0]
if not _ACTIVE_DATABASE.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run: tests truncate all tables, but DATABASE_URL points at "
        f"{_ACTIVE_DATABASE!r}, which is not a test database. "
        f"The database name must end in '_test'."
    )


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class FakeStorage(StorageBackend):
    """In-memory object store."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    async def put(
        self, stream: BinaryIO, *, key: str, content_type: str, size_bytes: int
    ) -> StoredFile:
        stream.seek(0)
        self.objects[key] = stream.read()
        self.content_types[key] = content_type
        return StoredFile(key=key, size_bytes=size_bytes, content_type=content_type)

    async def open(self, key: str) -> BinaryIO:
        import io

        if key not in self.objects:
            raise NotFoundError("Resume file not found.")
        return io.BytesIO(self.objects[key])

    async def presigned_url(self, key: str, *, filename: str) -> str | None:
        # None forces the streaming path, which is the one worth exercising.
        return None

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class FakeEmailBackend(EmailBackend):
    """Captures messages; can be told to fail to exercise the outbox."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.should_fail = False

    async def send(self, message: EmailMessage) -> SendResult:
        if self.should_fail:
            raise EmailSendError("simulated provider outage")
        self.sent.append(message)
        return SendResult(message_id=f"fake-{uuid.uuid4()}")

    def to(self, address: str) -> list[EmailMessage]:
        return [m for m in self.sent if m.to == address]


# --------------------------------------------------------------------------
# Database lifecycle
# --------------------------------------------------------------------------
async def _provision() -> None:
    database_url = settings.database_url
    admin_url, _, db_name = database_url.rpartition("/")

    admin_engine = create_async_engine(f"{admin_url}/postgres", isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    await admin_engine.dispose()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Empty the pool so the test event loop starts with fresh connections.
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    asyncio.run(_provision())


@pytest.fixture(autouse=True)
async def _clean_tables():
    """Truncate between tests so each one starts from a known empty state.

    The engine is disposed afterwards because pytest-asyncio runs each test in
    a fresh event loop: a pooled connection opened under the previous loop
    would otherwise be handed to the next test and fail with "attached to a
    different loop".
    """
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    try:
        yield
    finally:
        await engine.dispose()


@pytest.fixture
async def session():
    async with SessionFactory() as db_session:
        yield db_session


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------
@pytest.fixture
def storage(monkeypatch) -> FakeStorage:
    fake = FakeStorage()
    # LeadService imports the factory into its own namespace, so that is the
    # name that has to be patched.
    monkeypatch.setattr("app.services.lead.get_storage_backend", lambda: fake)
    return fake


@pytest.fixture
def mailer(monkeypatch) -> FakeEmailBackend:
    fake = FakeEmailBackend()
    monkeypatch.setattr("app.services.email.get_email_backend", lambda: fake)
    return fake


@pytest.fixture
async def client(storage: FakeStorage, mailer: FakeEmailBackend):
    # The rate limiter keeps per-IP counters in process memory, so without
    # this every test after the first ten would get a 429. The limiter itself
    # is covered directly in test_rate_limit.py.
    app.dependency_overrides[enforce_public_submit_rate_limit] = lambda: None

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def attorney(session) -> User:
    user = User(
        email="attorney@example.com",
        hashed_password=hash_password("changeme123"),
        full_name="Alma Attorney",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def auth_headers(client: AsyncClient, attorney: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "attorney@example.com", "password": "changeme123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --------------------------------------------------------------------------
# Sample files
# --------------------------------------------------------------------------
def pdf_bytes(payload: bytes = b"resume body") -> bytes:
    return b"%PDF-1.7\n" + payload + b"\n%%EOF\n"


def docx_bytes() -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def lead_payload(**overrides):
    """Multipart form fields for a valid submission."""
    data = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
    }
    data.update(overrides)
    return data


def resume_file(
    content: bytes | None = None,
    filename: str = "cv.pdf",
    content_type: str = "application/pdf",
):
    body = content if content is not None else pdf_bytes()
    return {"resume": (filename, body, content_type)}
