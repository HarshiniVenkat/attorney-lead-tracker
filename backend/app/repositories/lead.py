from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import LeadState
from app.models.lead import Lead, LeadStateEvent


@dataclass(slots=True, frozen=True)
class LeadFilters:
    state: LeadState | None = None
    search: str | None = None


SORTABLE_COLUMNS = {
    "created_at": Lead.created_at,
    "updated_at": Lead.updated_at,
    "last_name": Lead.last_name,
    "email": Lead.email,
    "state": Lead.state,
}


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_filters(self, stmt: Select, filters: LeadFilters) -> Select:
        if filters.state is not None:
            stmt = stmt.where(Lead.state == filters.state)

        if filters.search:
            # Escape LIKE wildcards so a literal % or _ in the query is matched
            # as itself rather than acting as a wildcard.
            term = filters.search.strip()
            for char in ("\\", "%", "_"):
                term = term.replace(char, f"\\{char}")
            pattern = f"%{term.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Lead.first_name).like(pattern, escape="\\"),
                    func.lower(Lead.last_name).like(pattern, escape="\\"),
                    func.lower(Lead.email).like(pattern, escape="\\"),
                    func.lower(Lead.first_name + " " + Lead.last_name).like(
                        pattern, escape="\\"
                    ),
                )
            )
        return stmt

    async def list_paginated(
        self,
        *,
        filters: LeadFilters,
        page: int,
        page_size: int,
        sort_by: str = "created_at",
        descending: bool = True,
    ) -> tuple[list[Lead], int]:
        column = SORTABLE_COLUMNS.get(sort_by, Lead.created_at)
        order = column.desc() if descending else column.asc()

        stmt = self._apply_filters(select(Lead), filters)
        # Tie-break on id so pagination is stable when timestamps collide.
        stmt = stmt.order_by(order, Lead.id.desc()).offset((page - 1) * page_size).limit(page_size)

        count_stmt = self._apply_filters(select(func.count(Lead.id)), filters)

        rows = (await self._session.execute(stmt)).unique().scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), total

    async def get_by_id(self, lead_id: uuid.UUID) -> Lead | None:
        stmt = select(Lead).where(Lead.id == lead_id)
        return (await self._session.execute(stmt)).unique().scalar_one_or_none()

    async def get_detail(self, lead_id: uuid.UUID) -> Lead | None:
        """Load a lead with its audit trail and delivery rows in one round trip."""
        stmt = (
            select(Lead)
            .where(Lead.id == lead_id)
            .options(
                selectinload(Lead.state_events).selectinload(LeadStateEvent.actor),
                selectinload(Lead.email_deliveries),
            )
            # Without this, re-reading a lead already in the identity map keeps
            # its stale collections - a just-written state event would be
            # missing from the response.
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).unique().scalar_one_or_none()

    def add(self, lead: Lead) -> Lead:
        self._session.add(lead)
        return lead

    def record_state_event(
        self,
        *,
        lead: Lead,
        from_state: LeadState | None,
        to_state: LeadState,
        actor_id: uuid.UUID | None,
        occurred_at: datetime,
    ) -> LeadStateEvent:
        event = LeadStateEvent(
            lead_id=lead.id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            created_at=occurred_at,
        )
        self._session.add(event)
        return event

    async def count_by_state(self) -> dict[LeadState, int]:
        """Counts for the admin filter tabs, in a single query."""
        stmt = select(Lead.state, func.count(Lead.id)).group_by(Lead.state)
        rows = (await self._session.execute(stmt)).all()
        counts = dict.fromkeys(LeadState, 0)
        counts.update(dict(rows))
        return counts
