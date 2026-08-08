"""Initial schema: users, leads, lead_state_events, email_deliveries

Revision ID: 0001
Revises:
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEAD_STATE = postgresql.ENUM(
    "PENDING", "REACHED_OUT", name="lead_state", create_type=False
)
EMAIL_KIND = postgresql.ENUM(
    "PROSPECT_CONFIRMATION", "ATTORNEY_NOTIFICATION", name="email_kind", create_type=False
)
EMAIL_DELIVERY_STATUS = postgresql.ENUM(
    "PENDING", "SENT", "FAILED", name="email_delivery_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # Enums are created once, explicitly, so the table definitions below can
    # reference them with create_type=False without racing each other.
    LEAD_STATE.create(bind, checkfirst=True)
    EMAIL_KIND.create(bind, checkfirst=True)
    EMAIL_DELIVERY_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("resume_key", sa.String(512), nullable=False),
        sa.Column("resume_filename", sa.String(255), nullable=False),
        sa.Column("resume_content_type", sa.String(127), nullable=False),
        sa.Column("resume_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("state", LEAD_STATE, nullable=False, server_default="PENDING"),
        sa.Column("reached_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reached_out_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Serves the default admin view: filter by state, newest first.
    op.create_index("ix_leads_state_created_at", "leads", ["state", "created_at"])
    op.create_index("ix_leads_email", "leads", ["email"])

    op.create_table(
        "lead_state_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", LEAD_STATE, nullable=True),
        sa.Column("to_state", LEAD_STATE, nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_lead_state_events_lead_id", "lead_state_events", ["lead_id"])

    op.create_table(
        "email_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", EMAIL_KIND, nullable=False),
        sa.Column("to_address", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column(
            "status", EMAIL_DELIVERY_STATUS, nullable=False, server_default="PENDING"
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        # Unused in v1; present so adding the retry worker needs no migration.
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_email_deliveries_lead_id", "email_deliveries", ["lead_id"])
    op.create_index("ix_email_deliveries_status", "email_deliveries", ["status"])


def downgrade() -> None:
    op.drop_table("email_deliveries")
    op.drop_table("lead_state_events")
    op.drop_table("leads")
    op.drop_table("users")

    bind = op.get_bind()
    EMAIL_DELIVERY_STATUS.drop(bind, checkfirst=True)
    EMAIL_KIND.drop(bind, checkfirst=True)
    LEAD_STATE.drop(bind, checkfirst=True)
