"""API routes for Chrome extension integration.

Receives metadata POSTed by the Chrome extension and passes it
to ImportAppService for buffering.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.web.app import get_import_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


# ============================================================
# Request / Response models
# ============================================================


class AuthorPayload(BaseModel):
    """Single author from the Chrome extension."""

    family: str = ""
    given: str = ""


class MetadataPayload(BaseModel):
    """Metadata payload sent by the Chrome extension.

    Mirrors the JSON structure produced by background.js postMetadataToBackend().
    """

    title: str = Field(..., min_length=1, description="Paper title (required)")
    doi: str | None = Field(None, description="DOI string or null")
    year: int | None = Field(None, description="Publication year or null")
    first_author: str | None = Field(None, description="First author family name")
    author_count: int = Field(0, ge=0, description="Total author count")
    authors: list[AuthorPayload] = Field(
        default_factory=list, description="Structured author list"
    )
    source: str = Field("unknown", description="Extraction source identifier")


class MetadataResponse(BaseModel):
    """Response after metadata reception."""

    status: str
    message: str


class DoiImportPayload(BaseModel):
    """Batch DOI import payload."""

    dois: list[str] = Field(..., min_length=1, description="DOIs to import")


class DoiImportResult(BaseModel):
    """Per-DOI import result."""

    doi: str
    status: Literal["registered", "duplicate", "failed"]
    title: str | None = None
    paper_id: str | None = None
    error: str | None = None


class DoiImportSummary(BaseModel):
    """Batch DOI import counters."""

    registered: int
    duplicate: int
    failed: int


class DoiImportResponse(BaseModel):
    """Batch DOI import response."""

    results: list[DoiImportResult]
    summary: DoiImportSummary


# ============================================================
# Endpoint
# ============================================================


@router.post(
    "/import/metadata",
    response_model=MetadataResponse,
    status_code=200,
)
async def receive_metadata(
    payload: MetadataPayload,
    request: Request,
) -> dict[str, Any]:
    """Receive metadata from the Chrome extension.

    Converts the payload into a domain Metadata object and buffers it
    via ImportAppService.receive_extension_metadata().
    """
    from src.domain.paper import DOI, Author, Metadata, PublicationYear

    try:
        # Build domain objects from payload
        doi = None
        if payload.doi:
            try:
                doi = DOI(payload.doi)
            except ValueError:
                logger.warning("Invalid DOI received: %s", payload.doi)
                # Continue without DOI rather than rejecting

        # Build authors list
        authors: list[Author] = []
        if payload.authors:
            for a in payload.authors:
                family = a.family.strip()
                if family:
                    authors.append(Author(family_name=family, given_name=a.given))

        # Fallback: use first_author if no structured authors provided
        if not authors and payload.first_author:
            authors.append(Author(family_name=payload.first_author))

        if not authors:
            raise HTTPException(
                status_code=422,
                detail="At least one author is required (authors list or first_author)",
            )

        # Build year
        year: PublicationYear | None = None
        if payload.year is not None:
            try:
                year = PublicationYear(payload.year)
            except ValueError as exc:
                logger.warning("Invalid year received: %s", payload.year)
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid publication year: {payload.year}",
                ) from exc

        if year is None:
            raise HTTPException(
                status_code=422,
                detail="Publication year is required",
            )

        metadata = Metadata(
            title=payload.title,
            authors=tuple(authors),
            year=year,
            doi=doi,
        )

        service = get_import_service(request)
        service.receive_extension_metadata(metadata)
        if metadata.doi is not None:
            service.register_metadata_only(metadata)

        logger.info(
            "Received metadata from extension: %s (DOI: %s)",
            payload.title[:80],
            payload.doi or "N/A",
        )

        return {
            "status": "ok",
            "message": f"Metadata buffered: {payload.title[:80]}",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process extension metadata")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {exc}",
        ) from exc


@router.post(
    "/import/doi",
    response_model=DoiImportResponse,
    response_model_exclude_none=True,
    status_code=200,
)
async def import_dois(
    payload: DoiImportPayload,
    request: Request,
) -> dict[str, Any]:
    """Import DOI-backed papers by resolving metadata through CrossRef."""
    from src.domain.paper import DOI, Author, Metadata, PublicationYear

    service = get_import_service(request)
    results: list[dict[str, Any]] = []
    summary = {"registered": 0, "duplicate": 0, "failed": 0}

    for raw_doi in payload.dois:
        try:
            doi = DOI(raw_doi)
        except ValueError as exc:
            summary["failed"] += 1
            results.append(
                {
                    "doi": raw_doi,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue

        try:
            metadata = Metadata(
                title=doi.value,
                authors=(Author(family_name="Unknown"),),
                year=PublicationYear(1900),
                doi=doi,
            )
            result = service.register_metadata_only(
                metadata,
                require_resolved=True,
            )
        except Exception as exc:
            logger.exception("Failed to import DOI: %s", doi.value)
            summary["failed"] += 1
            results.append(
                {
                    "doi": doi.value,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue

        paper = result.paper
        if result.status == "success" and paper is not None:
            summary["registered"] += 1
            results.append(
                {
                    "doi": doi.value,
                    "status": "registered",
                    "title": paper.metadata.title,
                    "paper_id": paper.id.value,
                }
            )
        elif result.status == "duplicate" and paper is not None:
            summary["duplicate"] += 1
            results.append(
                {
                    "doi": doi.value,
                    "status": "duplicate",
                    "title": paper.metadata.title,
                    "paper_id": paper.id.value,
                }
            )
        else:
            summary["failed"] += 1
            results.append(
                {
                    "doi": doi.value,
                    "status": "failed",
                    "error": result.message or "Metadata resolution failed",
                }
            )

    return {"results": results, "summary": summary}
