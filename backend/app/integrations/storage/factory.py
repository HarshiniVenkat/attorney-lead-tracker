from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.integrations.storage.base import StorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Resolve the configured storage adapter (cached for process lifetime)."""
    if settings.storage_backend == "local":
        from app.integrations.storage.local import build_local_storage

        return build_local_storage()

    from app.integrations.storage.s3 import build_s3_storage

    return build_s3_storage()
