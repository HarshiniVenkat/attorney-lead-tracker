"""The authenticated internal lead APIs."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import LeadState
from app.models.lead import Lead
from app.models.user import User
from tests.conftest import lead_payload, pdf_bytes, resume_file


async def create_lead(client: AsyncClient, **overrides) -> str:
    response = await client.post(
        "/api/v1/leads", data=lead_payload(**overrides), files=resume_file()
    )
    assert response.status_code == 201
    return response.json()["id"]


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
async def test_every_internal_route_requires_auth(client: AsyncClient):
    lead_id = await create_lead(client)

    for method, path in [
        ("get", "/api/v1/leads"),
        ("get", "/api/v1/leads/stats"),
        ("get", f"/api/v1/leads/{lead_id}"),
        ("get", f"/api/v1/leads/{lead_id}/resume"),
    ]:
        response = await getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} was not protected"

    patch = await client.patch(f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"})
    assert patch.status_code == 401


# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------
async def test_list_returns_leads_newest_first(
    client: AsyncClient, auth_headers: dict[str, str]
):
    await create_lead(client, first_name="First", email="first@example.com")
    await create_lead(client, first_name="Second", email="second@example.com")

    response = await client.get("/api/v1/leads", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["items"][0]["first_name"] == "Second"


async def test_list_is_paginated(client: AsyncClient, auth_headers: dict[str, str]):
    for index in range(5):
        await create_lead(client, email=f"lead{index}@example.com")

    response = await client.get(
        "/api/v1/leads?page=2&page_size=2", headers=auth_headers
    )

    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert body["total_pages"] == 3
    assert len(body["items"]) == 2


async def test_list_filters_by_state(client: AsyncClient, auth_headers: dict[str, str]):
    pending_id = await create_lead(client, email="pending@example.com")
    reached_id = await create_lead(client, email="reached@example.com")

    await client.patch(
        f"/api/v1/leads/{reached_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    pending = await client.get("/api/v1/leads?state=PENDING", headers=auth_headers)
    assert [item["id"] for item in pending.json()["items"]] == [pending_id]

    reached = await client.get("/api/v1/leads?state=REACHED_OUT", headers=auth_headers)
    assert [item["id"] for item in reached.json()["items"]] == [reached_id]


async def test_search_matches_name_and_email(
    client: AsyncClient, auth_headers: dict[str, str]
):
    await create_lead(client, first_name="Grace", last_name="Hopper", email="gh@example.com")
    await create_lead(client, first_name="Ada", last_name="Lovelace", email="al@example.com")

    for query, expected in [("grace", "Grace"), ("hopper", "Grace"), ("al@", "Ada")]:
        response = await client.get(f"/api/v1/leads?q={query}", headers=auth_headers)
        items = response.json()["items"]
        assert len(items) == 1, f"query {query!r} matched {len(items)} rows"
        assert items[0]["first_name"] == expected


async def test_search_matches_full_name(client: AsyncClient, auth_headers: dict[str, str]):
    await create_lead(client, first_name="Grace", last_name="Hopper", email="gh@example.com")

    response = await client.get("/api/v1/leads?q=grace hopper", headers=auth_headers)
    assert response.json()["total"] == 1


async def test_search_treats_wildcards_literally(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """A '%' in the query must not match every row."""
    await create_lead(client, first_name="Grace", email="gh@example.com")

    response = await client.get("/api/v1/leads?q=%25", headers=auth_headers)
    assert response.json()["total"] == 0


async def test_stats_counts_each_state(client: AsyncClient, auth_headers: dict[str, str]):
    first = await create_lead(client, email="a@example.com")
    await create_lead(client, email="b@example.com")
    await client.patch(
        f"/api/v1/leads/{first}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    response = await client.get("/api/v1/leads/stats", headers=auth_headers)
    assert response.json() == {"PENDING": 1, "REACHED_OUT": 1}


# --------------------------------------------------------------------------
# Detail
# --------------------------------------------------------------------------
async def test_detail_includes_audit_trail_and_delivery_status(
    client: AsyncClient, auth_headers: dict[str, str]
):
    lead_id = await create_lead(client)

    response = await client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["resume_filename"] == "cv.pdf"
    assert body["resume_size_bytes"] > 0
    assert len(body["state_events"]) == 1
    assert len(body["email_deliveries"]) == 2


async def test_unknown_lead_is_404(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get(f"/api/v1/leads/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_malformed_id_is_422(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/api/v1/leads/not-a-uuid", headers=auth_headers)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# State transitions
# --------------------------------------------------------------------------
async def test_marking_reached_out_records_the_attorney(
    client: AsyncClient, auth_headers: dict[str, str], attorney: User, session
):
    lead_id = await create_lead(client)

    response = await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "REACHED_OUT"
    assert body["reached_out_at"] is not None
    # Regression guard: assigning only the FK left this null in the response.
    assert body["reached_out_by"]["full_name"] == "Alma Attorney"

    lead = (await session.execute(select(Lead))).scalar_one()
    assert lead.state is LeadState.REACHED_OUT
    assert lead.reached_out_by_id == attorney.id


async def test_transition_appends_to_the_audit_trail(
    client: AsyncClient, auth_headers: dict[str, str]
):
    lead_id = await create_lead(client)

    response = await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    events = response.json()["state_events"]
    assert len(events) == 2
    assert events[0]["from_state"] is None
    assert events[0]["to_state"] == "PENDING"
    assert events[1]["from_state"] == "PENDING"
    assert events[1]["to_state"] == "REACHED_OUT"
    assert events[1]["actor"]["full_name"] == "Alma Attorney"


async def test_repeating_a_transition_conflicts(
    client: AsyncClient, auth_headers: dict[str, str]
):
    lead_id = await create_lead(client)
    await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    response = await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state_transition"


async def test_reverting_to_pending_conflicts(
    client: AsyncClient, auth_headers: dict[str, str]
):
    lead_id = await create_lead(client)
    await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )

    response = await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "PENDING"}, headers=auth_headers
    )
    assert response.status_code == 409


async def test_unknown_state_is_rejected(client: AsyncClient, auth_headers: dict[str, str]):
    lead_id = await create_lead(client)

    response = await client.patch(
        f"/api/v1/leads/{lead_id}", json={"state": "ARCHIVED"}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_transitioning_an_unknown_lead_is_404(
    client: AsyncClient, auth_headers: dict[str, str]
):
    response = await client.patch(
        f"/api/v1/leads/{uuid.uuid4()}",
        json={"state": "REACHED_OUT"},
        headers=auth_headers,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Resume download
# --------------------------------------------------------------------------
async def test_resume_downloads_with_the_original_filename(
    client: AsyncClient, auth_headers: dict[str, str]
):
    content = pdf_bytes(b"the actual resume")
    response = await client.post(
        "/api/v1/leads",
        data=lead_payload(),
        files={"resume": ("Ada_Lovelace_CV.pdf", content, "application/pdf")},
    )
    lead_id = response.json()["id"]

    download = await client.get(f"/api/v1/leads/{lead_id}/resume", headers=auth_headers)

    assert download.status_code == 200
    assert download.content == content
    assert download.headers["content-type"] == "application/pdf"
    assert "Ada_Lovelace_CV.pdf" in download.headers["content-disposition"]
