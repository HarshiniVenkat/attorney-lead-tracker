"""Operational CLI.

    python -m app.cli seed-admin
    python -m app.cli create-user --email a@b.com --name "A B" --password ...
    python -m app.cli deactivate-user --email a@b.com
"""

from __future__ import annotations

import asyncio

import typer

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import session_scope
from app.repositories.user import UserRepository
from app.services.auth import AuthService

app = typer.Typer(help="Alma leads backend operations.", no_args_is_help=True)


async def _create_user(email: str, password: str, full_name: str) -> str:
    async with session_scope() as session:
        users = UserRepository(session)
        if await users.get_by_email(email):
            return f"User already exists, leaving untouched: {email}"
        user = await AuthService(session).create_user(
            email=email, password=password, full_name=full_name
        )
        return f"Created attorney {user.email} ({user.id})"


@app.command("seed-admin")
def seed_admin() -> None:
    """Create the attorney account from SEED_ADMIN_* settings (idempotent)."""
    configure_logging()
    message = asyncio.run(
        _create_user(
            settings.seed_admin_email,
            settings.seed_admin_password,
            settings.seed_admin_name,
        )
    )
    typer.echo(message)

    if settings.is_production and settings.seed_admin_password == "changeme123":
        typer.secho(
            "WARNING: the default seed password is in use in production.",
            fg=typer.colors.RED,
            err=True,
        )


@app.command("create-user")
def create_user(
    email: str = typer.Option(..., help="Attorney email address."),
    password: str = typer.Option(..., prompt=True, hide_input=True),
    name: str = typer.Option(..., help="Full name."),
) -> None:
    """Create an additional attorney account."""
    configure_logging()
    typer.echo(asyncio.run(_create_user(email, password, name)))


async def _set_active(email: str, is_active: bool) -> str:
    async with session_scope() as session:
        user = await UserRepository(session).get_by_email(email)
        if user is None:
            return f"No such user: {email}"
        user.is_active = is_active
        return f"{'Activated' if is_active else 'Deactivated'} {user.email}"


@app.command("deactivate-user")
def deactivate_user(email: str = typer.Option(..., help="Attorney email address.")) -> None:
    """Revoke an attorney's access while preserving their audit trail."""
    configure_logging()
    typer.echo(asyncio.run(_set_active(email, False)))


@app.command("activate-user")
def activate_user(email: str = typer.Option(..., help="Attorney email address.")) -> None:
    """Restore a deactivated attorney's access."""
    configure_logging()
    typer.echo(asyncio.run(_set_active(email, True)))


if __name__ == "__main__":
    app()
