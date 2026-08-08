"""The public lead intake endpoint."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.email_delivery import EmailDelivery
from app.models.enums import EmailDeliveryStatus, EmailKind, LeadState
from app.models.lead import Lead, LeadStateEvent
from tests.conftest import (
    FakeEmailBackend,
    FakeStorage,
    docx_bytes,
    lead_payload,
    pdf_bytes,
    resume_file,
)


async def test_submitting_a_lead_creates_it(client: AsyncClient, session):
    response = await client.post(
        "/api/v1/leads", data=lead_payload(), files=resume_file()
    )

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "PENDING"
    assert body["id"]

    lead = (await session.execute(select(Lead))).scalar_one()
    assert lead.first_name == "Ada"
    assert lead.email == "ada@example.com"
    assert lead.state is LeadState.PENDING
    assert lead.reached_out_at is None


async def test_no_authentication_is_required(client: AsyncClient):
    """The form is public; that is the whole point of this endpoint."""
    response = await client.post(
        "/api/v1/leads", data=lead_payload(), files=resume_file()
    )
    assert response.status_code == 201


async def test_response_does_not_leak_internal_fields(client: AsyncClient):
    response = await client.post(
        "/api/v1/leads", data=lead_payload(), files=resume_file()
    )

    # A public caller gets an id and a state, nothing more.
    assert set(response.json()) == {"id", "state", "created_at"}


async def test_resume_is_stored_under_a_generated_key(
    client: AsyncClient, session, storage: FakeStorage
):
    content = pdf_bytes(b"unique-content")
    response = await client.post(
        "/api/v1/leads",
        data=lead_payload(),
        files={"resume": ("../../etc/passwd.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201

    lead = (await session.execute(select(Lead))).scalar_one()

    # The prospect's filename is recorded but never used as the storage key,
    # so a traversal attempt cannot escape the key namespace.
    assert lead.resume_filename == "../../etc/passwd.pdf"
    assert lead.resume_key.startswith(f"leads/{lead.id}/resume-")
    assert ".." not in lead.resume_key
    assert storage.objects[lead.resume_key] == content


async def test_email_is_lowercased(client: AsyncClient, session):
    await client.post(
        "/api/v1/leads",
        data=lead_payload(email="Ada.Lovelace@Example.COM"),
        files=resume_file(),
    )

    lead = (await session.execute(select(Lead))).scalar_one()
    assert lead.email == "ada.lovelace@example.com"


async def test_names_are_trimmed(client: AsyncClient, session):
    await client.post(
        "/api/v1/leads",
        data=lead_payload(first_name="  Ada  ", last_name="  Lovelace  "),
        files=resume_file(),
    )

    lead = (await session.execute(select(Lead))).scalar_one()
    assert lead.first_name == "Ada"
    assert lead.last_name == "Lovelace"


async def test_docx_is_accepted(client: AsyncClient, session):
    response = await client.post(
        "/api/v1/leads",
        data=lead_payload(),
        files=resume_file(docx_bytes(), "cv.docx", "application/octet-stream"),
    )

    assert response.status_code == 201
    lead = (await session.execute(select(Lead))).scalar_one()
    assert lead.resume_content_type.endswith("wordprocessingml.document")


async def test_creation_records_an_initial_state_event(client: AsyncClient, session):
    await client.post("/api/v1/leads", data=lead_payload(), files=resume_file())

    event = (await session.execute(select(LeadStateEvent))).scalar_one()
    assert event.from_state is None
    assert event.to_state is LeadState.PENDING
    # Submitted by the prospect, so there is no attorney to attribute it to.
    assert event.actor_id is None


# --------------------------------------------------------------------------
# The transactional outbox
# --------------------------------------------------------------------------
async def test_both_emails_are_enqueued_and_sent(
    client: AsyncClient, session, mailer: FakeEmailBackend
):
    await client.post("/api/v1/leads", data=lead_payload(), files=resume_file())

    deliveries = (await session.execute(select(EmailDelivery))).scalars().all()
    assert {d.kind for d in deliveries} == {
        EmailKind.PROSPECT_CONFIRMATION,
        EmailKind.ATTORNEY_NOTIFICATION,
    }
    assert all(d.status is EmailDeliveryStatus.SENT for d in deliveries)
    assert all(d.attempts == 1 for d in deliveries)

    assert len(mailer.to("ada@example.com")) == 1
    assert len(mailer.to("attorney@example.com")) == 1


async def test_prospect_email_addresses_them_by_name(
    client: AsyncClient, mailer: FakeEmailBackend
):
    await client.post("/api/v1/leads", data=lead_payload(), files=resume_file())

    message = mailer.to("ada@example.com")[0]
    assert "Ada" in message.subject
    assert "Ada" in message.text_body
    assert "<!doctype html>" in message.html_body.lower()


async def test_attorney_email_links_to_the_lead(
    client: AsyncClient, session, mailer: FakeEmailBackend
):
    await client.post("/api/v1/leads", data=lead_payload(), files=resume_file())

    lead = (await session.execute(select(Lead))).scalar_one()
    message = mailer.to("attorney@example.com")[0]

    assert str(lead.id) in message.text_body
    assert "Ada Lovelace" in message.subject
    # Reply-to points at the prospect so hitting reply just works.
    assert message.reply_to == "ada@example.com"


async def test_email_failure_does_not_fail_the_submission(
    client: AsyncClient, session, mailer: FakeEmailBackend
):
    """The headline guarantee of the outbox design.

    A dead mail provider must not cost us the lead, and must not show the
    prospect an error that makes them submit again.
    """
    mailer.should_fail = True

    response = await client.post(
        "/api/v1/leads", data=lead_payload(), files=resume_file()
    )

    assert response.status_code == 201

    lead = (await session.execute(select(Lead))).scalar_one()
    assert lead.state is LeadState.PENDING

    deliveries = (await session.execute(select(EmailDelivery))).scalars().all()
    assert len(deliveries) == 2
    # The failure is recorded, not lost: this is what makes it recoverable and
    # visible in the admin UI.
    assert all(d.status is EmailDeliveryStatus.FAILED for d in deliveries)
    assert all(d.attempts == 1 for d in deliveries)
    assert all("simulated provider outage" in (d.last_error or "") for d in deliveries)


async def test_delivery_rows_reference_the_right_recipients(client: AsyncClient, session):
    await client.post(
        "/api/v1/leads", data=lead_payload(email="grace@example.com"), files=resume_file()
    )

    deliveries = (await session.execute(select(EmailDelivery))).scalars().all()
    by_kind = {d.kind: d for d in deliveries}

    assert by_kind[EmailKind.PROSPECT_CONFIRMATION].to_address == "grace@example.com"
    assert by_kind[EmailKind.ATTORNEY_NOTIFICATION].to_address == "attorney@example.com"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
async def test_missing_resume_is_rejected(client: AsyncClient):
    response = await client.post("/api/v1/leads", data=lead_payload())
    assert response.status_code == 422


async def test_invalid_email_is_rejected_with_a_field_error(client: AsyncClient):
    response = await client.post(
        "/api/v1/leads", data=lead_payload(email="not-an-email"), files=resume_file()
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    # The form needs to know *which* field to mark.
    assert "email" in body["error"]["details"]["fields"]


async def test_blank_name_is_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/leads", data=lead_payload(first_name="   "), files=resume_file()
    )

    assert response.status_code == 422
    assert "first_name" in response.json()["error"]["details"]["fields"]


async def test_spoofed_resume_is_rejected(client: AsyncClient, session):
    response = await client.post(
        "/api/v1/leads",
        data=lead_payload(),
        files={"resume": ("resume.pdf", b"MZ\x90\x00 binary", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"
    # Nothing is persisted when validation fails.
    assert (await session.execute(select(Lead))).first() is None


async def test_oversized_resume_is_rejected(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.services.lead.settings.max_resume_size_bytes", 512)

    response = await client.post(
        "/api/v1/leads",
        data=lead_payload(),
        files=resume_file(pdf_bytes(b"x" * 4096)),
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_failed_validation_leaves_no_orphan_delivery_rows(
    client: AsyncClient, session
):
    await client.post(
        "/api/v1/leads",
        data=lead_payload(email="bad"),
        files=resume_file(),
    )

    assert (await session.execute(select(EmailDelivery))).first() is None
