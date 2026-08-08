"""Resume upload validation.

The browser's `accept` attribute and the declared Content-Type are both
trivially forged, so the authoritative check here is magic-byte sniffing of the
bytes actually received. Size is enforced with a running counter while
streaming rather than by trusting Content-Length.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, Final

from fastapi import UploadFile

from app.core.errors import (
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ValidationError,
)

CHUNK_SIZE: Final = 64 * 1024
SPOOL_MAX_BYTES: Final = 1024 * 1024   # beyond this the buffer rolls to disk

PDF_MAGIC: Final = b"%PDF-"
ZIP_LOCAL_FILE_HEADER: Final = b"PK\x03\x04"

CONTENT_TYPE_PDF: Final = "application/pdf"
CONTENT_TYPE_DOCX: Final = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

ALLOWED_EXTENSIONS: Final = frozenset({".pdf", ".docx"})
_EXTENSION_BY_CONTENT_TYPE: Final = {
    CONTENT_TYPE_PDF: ".pdf",
    CONTENT_TYPE_DOCX: ".docx",
}

_UNSUPPORTED_MESSAGE: Final = "Resume must be a PDF or DOCX file."


@dataclass(slots=True)
class ValidatedUpload:
    """A resume that passed every check, buffered and rewound for storage."""

    stream: BinaryIO
    size_bytes: int
    content_type: str
    extension: str
    original_filename: str


def _human_size(num_bytes: int) -> str:
    """Format a byte cap for an end-user message, without rounding to '0 MB'."""
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.0f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes} bytes"


def _extension_of(filename: str) -> str:
    _, dot, suffix = filename.rpartition(".")
    return f".{suffix.lower()}" if dot else ""


def _sniff_content_type(stream: BinaryIO) -> str | None:
    """Identify the file from its bytes. Returns None if unrecognised."""
    stream.seek(0)
    header = stream.read(8)
    stream.seek(0)

    if header.startswith(PDF_MAGIC):
        return CONTENT_TYPE_PDF

    if header.startswith(ZIP_LOCAL_FILE_HEADER):
        # A DOCX is a zip; confirm it is a Word document and not any old
        # archive renamed. Only the central directory is read - nothing is
        # extracted, so a zip bomb has nothing to expand into.
        try:
            with zipfile.ZipFile(stream) as archive:
                names = archive.namelist()
        except zipfile.BadZipFile:
            return None
        finally:
            stream.seek(0)

        if "[Content_Types].xml" in names and any(n.startswith("word/") for n in names):
            return CONTENT_TYPE_DOCX

    return None


async def read_and_validate_resume(
    upload: UploadFile, *, max_bytes: int
) -> ValidatedUpload:
    """Buffer the upload, enforcing type and size. Caller owns closing the stream."""
    filename = (upload.filename or "").strip()
    if not filename:
        raise ValidationError(
            "A resume file is required.", details={"fields": {"resume": "This field is required."}}
        )

    extension = _extension_of(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedMediaTypeError(_UNSUPPORTED_MESSAGE)

    buffer: BinaryIO = SpooledTemporaryFile(max_size=SPOOL_MAX_BYTES)
    size = 0
    try:
        while chunk := await upload.read(CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise PayloadTooLargeError(
                    f"Resume must be smaller than {_human_size(max_bytes)}."
                )
            buffer.write(chunk)

        if size == 0:
            raise ValidationError(
                "The uploaded resume is empty.",
                details={"fields": {"resume": "The uploaded file is empty."}},
            )

        detected = _sniff_content_type(buffer)
        if detected is None:
            raise UnsupportedMediaTypeError(_UNSUPPORTED_MESSAGE)

        # Trust the bytes over the filename: a PDF named .docx is stored as a
        # PDF so the attorney's browser opens it correctly.
        buffer.seek(0)
        return ValidatedUpload(
            stream=buffer,
            size_bytes=size,
            content_type=detected,
            extension=_EXTENSION_BY_CONTENT_TYPE[detected],
            original_filename=filename,
        )
    except Exception:
        buffer.close()
        raise
    finally:
        await upload.close()
