"""Storage port.

Resume files sit behind this interface so the S3 adapter can be swapped for
local disk in dev and an in-memory fake in tests, with no change to callers.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(slots=True)
class StoredFile:
    key: str
    size_bytes: int
    content_type: str


class StorageBackend(ABC):
    @abstractmethod
    async def put(
        self,
        stream: BinaryIO,
        *,
        key: str,
        content_type: str,
        size_bytes: int,
    ) -> StoredFile:
        """Persist the stream under `key`."""

    @abstractmethod
    async def open(self, key: str) -> BinaryIO:
        """Return a readable handle for `key`. Raises NotFoundError if absent."""

    @abstractmethod
    async def presigned_url(self, key: str, *, filename: str) -> str | None:
        """Time-limited direct download URL, or None if unsupported."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove `key`. Absent keys are not an error."""

    @staticmethod
    def build_key(lead_id: uuid.UUID, extension: str) -> str:
        """Generate an opaque storage key.

        The prospect's filename never appears here: it is attacker-controlled
        and would otherwise open up path traversal and cross-lead overwrites.
        """
        return f"leads/{lead_id}/resume-{uuid.uuid4().hex}{extension}"
