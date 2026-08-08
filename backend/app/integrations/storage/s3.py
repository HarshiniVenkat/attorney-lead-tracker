"""S3 / MinIO storage adapter.

boto3 is synchronous, so every call is pushed to a worker thread to keep the
event loop free.
"""

from __future__ import annotations

import logging
from typing import Any, BinaryIO
from urllib.parse import quote

import boto3
from anyio import to_thread
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.errors import NotFoundError, StorageError
from app.integrations.storage.base import StorageBackend, StoredFile

logger = logging.getLogger(__name__)


class S3Storage(StorageBackend):
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
        public_endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        url_ttl_seconds: int = 300,
    ) -> None:
        self._bucket = bucket
        self._url_ttl = url_ttl_seconds
        self._client_kwargs: dict[str, Any] = {
            "region_name": region,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            # MinIO only speaks the v4 path-style addressing.
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        self._client = boto3.client("s3", endpoint_url=endpoint_url, **self._client_kwargs)

        # Presigned URLs are opened by the attorney's browser, which resolves
        # `localhost`, not the compose-internal `minio` hostname. Signing them
        # with a separate client keeps both addresses correct.
        self._signing_client = (
            boto3.client("s3", endpoint_url=public_endpoint_url, **self._client_kwargs)
            if public_endpoint_url and public_endpoint_url != endpoint_url
            else self._client
        )

    async def put(
        self, stream: BinaryIO, *, key: str, content_type: str, size_bytes: int
    ) -> StoredFile:
        def _upload() -> None:
            stream.seek(0)
            self._client.upload_fileobj(
                stream,
                self._bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )

        try:
            await to_thread.run_sync(_upload)
        except (BotoCoreError, ClientError) as exc:
            logger.exception("s3_upload_failed", extra={"key": key})
            raise StorageError("Could not store the uploaded file.") from exc

        return StoredFile(key=key, size_bytes=size_bytes, content_type=content_type)

    async def open(self, key: str) -> BinaryIO:
        def _get() -> BinaryIO:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"]

        try:
            return await to_thread.run_sync(_get)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise NotFoundError("Resume file not found.") from exc
            raise StorageError("Could not read the stored file.") from exc

    async def presigned_url(self, key: str, *, filename: str) -> str | None:
        def _sign() -> str:
            return self._signing_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    # Give the download the prospect's original filename.
                    "ResponseContentDisposition": (
                        f'attachment; filename="{quote(filename)}"'
                    ),
                },
                ExpiresIn=self._url_ttl,
            )

        try:
            return await to_thread.run_sync(_sign)
        except (BotoCoreError, ClientError):
            logger.exception("s3_presign_failed", extra={"key": key})
            return None   # caller falls back to streaming through the API

    async def delete(self, key: str) -> None:
        def _delete() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=key)

        try:
            await to_thread.run_sync(_delete)
        except (BotoCoreError, ClientError):
            logger.warning("s3_delete_failed", extra={"key": key})


def build_s3_storage() -> S3Storage:
    return S3Storage(
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        public_endpoint_url=settings.s3_public_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        url_ttl_seconds=settings.presigned_url_ttl_seconds,
    )
