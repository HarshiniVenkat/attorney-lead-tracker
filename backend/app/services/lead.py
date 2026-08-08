from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.integrations.storage.base import StorageBackend
from app.integrations.storage.factory import get_storage_backend
from app.models.enums import LeadState
from app.models.lead import Lead
from app.models.user import User
from app.repositories.lead import LeadFilters, LeadRepository
from app.services.email import EmailService
from app.services.state_machine import assert_can_transition
from app.validators.upload import read_and_validate_resume

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ResumeDownload:
    """Either a redirect target or a stream, depending on the backend."""

    url: str | None
    stream: BinaryIO | None
    filename: str
    content_type: str


class LeadService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageBackend | None = None,
        email_service: EmailService | None = None,
    ) -> None:
        self._session = session
        self._leads = LeadRepository(session)
        self._storage = storage or get_storage_backend()
        self._emails = email_service or EmailService(session)

    async def create_lead(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        resume: UploadFile,
    ) -> Lead:
        """Validate, store the resume, persist the lead and its outbox rows.

        The resume is uploaded to object storage *before* the transaction
        commits. A crash between the two leaves an orphaned file, which is
        harmless and cheap to sweep; the reverse order would leave a lead row
        pointing at a resume that does not exist.
        """
        validated = await read_and_validate_resume(
            resume, max_bytes=settings.max_resume_size_bytes
        )

        lead_id = uuid.uuid4()
        key = StorageBackend.build_key(lead_id, validated.extension)

        try:
            stored = await self._storage.put(
                validated.stream,
                key=key,
                content_type=validated.content_type,
                size_bytes=validated.size_bytes,
            )
        finally:
            validated.stream.close()

        lead = Lead(
            id=lead_id,
            first_name=first_name,
            last_name=last_name,
            email=email.strip().lower(),
            resume_key=stored.key,
            resume_filename=validated.original_filename,
            resume_content_type=stored.content_type,
            resume_size_bytes=stored.size_bytes,
            state=LeadState.PENDING,
        )
        self._leads.add(lead)
        await self._session.flush()

        self._leads.record_state_event(
            lead=lead,
            from_state=None,
            to_state=LeadState.PENDING,
            actor_id=None,          # created by the prospect, not an attorney
            occurred_at=datetime.now(UTC),
        )

        # Staged, not sent. These rows commit atomically with the lead above,
        # so the lead can never exist without a durable record of the emails
        # owed on it. Delivery is attempted after commit, off the request path.
        self._emails.enqueue_lead_emails(lead)

        # Commit here rather than leaving it to the request-scoped dependency.
        # The background dispatcher runs in its own session and would otherwise
        # race this transaction and find no lead to send for.
        await self._session.commit()
        logger.info(
            "lead_created",
            extra={"lead_id": str(lead.id), "resume_size_bytes": stored.size_bytes},
        )
        return lead

    async def list_leads(
        self,
        *,
        state: LeadState | None,
        search: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        descending: bool,
    ) -> tuple[list[Lead], int]:
        return await self._leads.list_paginated(
            filters=LeadFilters(state=state, search=search),
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            descending=descending,
        )

    async def get_lead_detail(self, lead_id: uuid.UUID) -> Lead:
        lead = await self._leads.get_detail(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found.")
        return lead

    async def transition_state(
        self, *, lead_id: uuid.UUID, target_state: LeadState, actor: User
    ) -> Lead:
        lead = await self._leads.get_detail(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found.")

        assert_can_transition(lead.state, target_state)

        previous_state = lead.state
        now = datetime.now(UTC)

        lead.state = target_state
        if target_state is LeadState.REACHED_OUT:
            lead.reached_out_at = now
            # Assign the relationship, not just the FK: setting the id alone
            # leaves the already-loaded `reached_out_by` on this instance as
            # None, and the response would serialise a null attorney.
            lead.reached_out_by = actor

        self._leads.record_state_event(
            lead=lead,
            from_state=previous_state,
            to_state=target_state,
            actor_id=actor.id,
            occurred_at=now,
        )
        await self._session.flush()

        logger.info(
            "lead_state_changed",
            extra={
                "lead_id": str(lead.id),
                "from_state": previous_state.value,
                "to_state": target_state.value,
                "actor_id": str(actor.id),
            },
        )
        # Re-read so the response carries the freshly written audit trail.
        return await self.get_lead_detail(lead_id)

    async def get_resume_download(self, lead_id: uuid.UUID) -> ResumeDownload:
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found.")

        # Prefer a presigned URL so the file bytes bypass the API entirely.
        url = await self._storage.presigned_url(
            lead.resume_key, filename=lead.resume_filename
        )
        if url:
            return ResumeDownload(
                url=url,
                stream=None,
                filename=lead.resume_filename,
                content_type=lead.resume_content_type,
            )

        return ResumeDownload(
            url=None,
            stream=await self._storage.open(lead.resume_key),
            filename=lead.resume_filename,
            content_type=lead.resume_content_type,
        )

    async def state_counts(self) -> dict[LeadState, int]:
        return await self._leads.count_by_state()
