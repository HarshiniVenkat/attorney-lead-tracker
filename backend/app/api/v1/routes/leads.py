from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import ValidationError as PydanticValidationError

from app.api.deps import CurrentUser, LeadServiceDep, Pagination
from app.core.errors import ValidationError
from app.core.rate_limit import enforce_public_submit_rate_limit
from app.models.enums import LeadState
from app.schemas.common import ErrorResponse, Page
from app.schemas.lead import (
    LeadCreatedResponse,
    LeadCreateForm,
    LeadDetail,
    LeadListItem,
    LeadUpdateRequest,
)
from app.services.email import dispatch_lead_emails_task

public_router = APIRouter(prefix="/leads", tags=["leads (public)"])
router = APIRouter(prefix="/leads", tags=["leads (internal)"])

STREAM_CHUNK_SIZE = 64 * 1024


def _as_field_errors(exc: PydanticValidationError) -> ValidationError:
    """Convert a manual model validation into the standard 422 envelope."""
    fields = {
        ".".join(str(part) for part in error["loc"]) or "__root__": error["msg"]
        for error in exc.errors()
    }
    return ValidationError(
        "The submitted data is invalid.", details={"fields": fields}
    )


@public_router.post(
    "",
    response_model=LeadCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a lead (public, unauthenticated)",
    dependencies=[Depends(enforce_public_submit_rate_limit)],
    responses={
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
async def create_lead(
    background_tasks: BackgroundTasks,
    lead_service: LeadServiceDep,
    first_name: Annotated[str, Form(max_length=100)],
    last_name: Annotated[str, Form(max_length=100)],
    email: Annotated[str, Form(max_length=320)],
    resume: Annotated[UploadFile, File(description="PDF or DOCX, max 5 MB.")],
) -> LeadCreatedResponse:
    try:
        form = LeadCreateForm(first_name=first_name, last_name=last_name, email=email)
    except PydanticValidationError as exc:
        raise _as_field_errors(exc) from exc

    lead = await lead_service.create_lead(
        first_name=form.first_name,
        last_name=form.last_name,
        email=form.email,
        resume=resume,
    )

    # Runs after the response is sent, and therefore after the request
    # transaction (including the outbox rows) has committed. If it fails, the
    # rows stay FAILED and are visible in the admin UI - the prospect is never
    # shown an error for a mail problem.
    background_tasks.add_task(dispatch_lead_emails_task, lead.id)

    return LeadCreatedResponse.model_validate(lead)


@router.get(
    "",
    response_model=Page[LeadListItem],
    summary="List leads",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def list_leads(
    _: CurrentUser,
    lead_service: LeadServiceDep,
    pagination: Pagination,
    state: Annotated[LeadState | None, Query(description="Filter by lead state.")] = None,
    q: Annotated[
        str | None, Query(max_length=200, description="Search first name, last name or email.")
    ] = None,
    sort_by: Annotated[
        str, Query(pattern="^(created_at|updated_at|last_name|email|state)$")
    ] = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[LeadListItem]:
    leads, total = await lead_service.list_leads(
        state=state,
        search=q,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        descending=order == "desc",
    )
    return Page.build(
        items=[LeadListItem.model_validate(lead) for lead in leads],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/stats",
    response_model=dict[str, int],
    summary="Lead counts per state, for the filter tabs",
)
async def lead_stats(_: CurrentUser, lead_service: LeadServiceDep) -> dict[str, int]:
    counts = await lead_service.state_counts()
    return {state.value: count for state, count in counts.items()}


@router.get(
    "/{lead_id}",
    response_model=LeadDetail,
    summary="Get a single lead with its audit trail and email delivery status",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_lead(
    lead_id: uuid.UUID, _: CurrentUser, lead_service: LeadServiceDep
) -> LeadDetail:
    return LeadDetail.model_validate(await lead_service.get_lead_detail(lead_id))


@router.patch(
    "/{lead_id}",
    response_model=LeadDetail,
    summary="Transition a lead's state",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The requested transition is not legal from the current state.",
        },
    },
)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdateRequest,
    current_user: CurrentUser,
    lead_service: LeadServiceDep,
) -> LeadDetail:
    lead = await lead_service.transition_state(
        lead_id=lead_id, target_state=payload.state, actor=current_user
    )
    return LeadDetail.model_validate(lead)


@router.get(
    "/{lead_id}/resume",
    summary="Download a lead's resume",
    # The handler returns a redirect or a stream depending on the storage
    # backend, so there is no response model for FastAPI to infer.
    response_model=None,
    response_class=StreamingResponse,
    responses={
        status.HTTP_302_FOUND: {"description": "Redirect to a presigned object-store URL."},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def download_resume(
    lead_id: uuid.UUID, _: CurrentUser, lead_service: LeadServiceDep
) -> RedirectResponse | StreamingResponse:
    download = await lead_service.get_resume_download(lead_id)

    if download.url:
        # Short-lived presigned URL: the bytes never pass through the API.
        return RedirectResponse(url=download.url, status_code=status.HTTP_302_FOUND)

    assert download.stream is not None

    def _iter_file():
        try:
            while chunk := download.stream.read(STREAM_CHUNK_SIZE):
                yield chunk
        finally:
            download.stream.close()

    # RFC 5987 filename* keeps non-ASCII resume names intact.
    disposition = (
        f"attachment; filename=\"{download.filename}\"; "
        f"filename*=UTF-8''{quote(download.filename)}"
    )
    return StreamingResponse(
        _iter_file(),
        media_type=download.content_type,
        headers={"Content-Disposition": disposition},
    )
