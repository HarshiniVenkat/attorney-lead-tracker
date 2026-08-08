"""Unit tests for resume upload validation.

The point of these is that the *bytes* decide, not the filename or the
declared content type - both of which the client controls.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import UploadFile

from app.core.errors import (
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from app.validators.upload import (
    CONTENT_TYPE_DOCX,
    CONTENT_TYPE_PDF,
    read_and_validate_resume,
)
from tests.conftest import docx_bytes, pdf_bytes

FIVE_MB = 5 * 1024 * 1024


def upload(content: bytes, filename: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content))


async def test_accepts_pdf():
    result = await read_and_validate_resume(upload(pdf_bytes(), "cv.pdf"), max_bytes=FIVE_MB)

    assert result.content_type == CONTENT_TYPE_PDF
    assert result.extension == ".pdf"
    assert result.original_filename == "cv.pdf"
    result.stream.close()


async def test_accepts_docx():
    result = await read_and_validate_resume(upload(docx_bytes(), "cv.docx"), max_bytes=FIVE_MB)

    assert result.content_type == CONTENT_TYPE_DOCX
    assert result.extension == ".docx"
    result.stream.close()


async def test_executable_renamed_to_pdf_is_rejected():
    """The headline case: a spoofed extension must not get through."""
    with pytest.raises(UnsupportedMediaTypeError):
        await read_and_validate_resume(
            upload(b"MZ\x90\x00 this is a PE binary", "resume.pdf"), max_bytes=FIVE_MB
        )


async def test_plain_zip_renamed_to_docx_is_rejected():
    """A DOCX is a zip, but not every zip is a DOCX."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello")

    with pytest.raises(UnsupportedMediaTypeError):
        await read_and_validate_resume(
            upload(buffer.getvalue(), "resume.docx"), max_bytes=FIVE_MB
        )


async def test_disallowed_extension_is_rejected():
    with pytest.raises(UnsupportedMediaTypeError):
        await read_and_validate_resume(upload(pdf_bytes(), "cv.txt"), max_bytes=FIVE_MB)


async def test_lying_content_type_does_not_help():
    """The declared content type is ignored entirely."""
    file = UploadFile(
        filename="cv.pdf",
        file=io.BytesIO(b"not a pdf at all"),
        headers={"content-type": "application/pdf"},  # type: ignore[arg-type]
    )
    with pytest.raises(UnsupportedMediaTypeError):
        await read_and_validate_resume(file, max_bytes=FIVE_MB)


async def test_empty_file_is_rejected():
    with pytest.raises(ValidationError):
        await read_and_validate_resume(upload(b"", "cv.pdf"), max_bytes=FIVE_MB)


async def test_missing_filename_is_rejected():
    with pytest.raises(ValidationError):
        await read_and_validate_resume(upload(pdf_bytes(), ""), max_bytes=FIVE_MB)


async def test_oversized_file_is_rejected():
    oversized = pdf_bytes(b"x" * 2048)
    with pytest.raises(PayloadTooLargeError) as exc_info:
        await read_and_validate_resume(upload(oversized, "cv.pdf"), max_bytes=1024)

    # The cap is reported in units the user can act on.
    assert "1 KB" in exc_info.value.message


async def test_content_wins_over_extension():
    """A PDF named .docx is stored as a PDF, so it opens correctly later."""
    result = await read_and_validate_resume(
        upload(pdf_bytes(), "resume.docx"), max_bytes=FIVE_MB
    )

    assert result.content_type == CONTENT_TYPE_PDF
    assert result.extension == ".pdf"
    assert result.original_filename == "resume.docx"
    result.stream.close()


async def test_size_is_measured_from_the_stream():
    content = pdf_bytes(b"y" * 500)
    result = await read_and_validate_resume(upload(content, "cv.pdf"), max_bytes=FIVE_MB)

    assert result.size_bytes == len(content)
    result.stream.close()
