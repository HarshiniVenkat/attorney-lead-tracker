"""Local-disk storage adapter, for running without an object store."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import BinaryIO

from anyio import to_thread

from app.core.config import settings
from app.core.errors import NotFoundError, StorageError
from app.integrations.storage.base import StorageBackend, StoredFile

logger = logging.getLogger(__name__)


class LocalStorage(StorageBackend):
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        # Keys are generated server-side, but resolve and re-check anyway:
        # a traversal bug elsewhere shouldn't become an arbitrary file write.
        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise StorageError("Invalid storage key.")
        return candidate

    async def put(
        self, stream: BinaryIO, *, key: str, content_type: str, size_bytes: int
    ) -> StoredFile:
        path = self._path_for(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream.seek(0)
            with path.open("wb") as handle:
                shutil.copyfileobj(stream, handle)

        try:
            await to_thread.run_sync(_write)
        except OSError as exc:
            logger.exception("local_storage_write_failed", extra={"key": key})
            raise StorageError("Could not store the uploaded file.") from exc

        return StoredFile(key=key, size_bytes=size_bytes, content_type=content_type)

    async def open(self, key: str) -> BinaryIO:
        path = self._path_for(key)
        if not path.is_file():
            raise NotFoundError("Resume file not found.")
        return path.open("rb")

    async def presigned_url(self, key: str, *, filename: str) -> str | None:
        return None   # no direct URL; the API streams the bytes instead

    async def delete(self, key: str) -> None:
        try:
            self._path_for(key).unlink(missing_ok=True)
        except OSError:
            logger.warning("local_storage_delete_failed", extra={"key": key})


def build_local_storage() -> LocalStorage:
    return LocalStorage(settings.local_storage_dir)
