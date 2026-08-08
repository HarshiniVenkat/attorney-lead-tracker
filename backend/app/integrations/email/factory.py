from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.integrations.email.base import EmailBackend


@lru_cache
def get_email_backend() -> EmailBackend:
    """Resolve the configured email adapter (cached for process lifetime)."""
    from app.integrations.email.smtp import ConsoleEmailBackend, build_smtp_backend

    if settings.email_backend == "console":
        return ConsoleEmailBackend()
    return build_smtp_backend()
