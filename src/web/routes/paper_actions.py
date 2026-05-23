"""Paper action routes: delete and other destructive operations.

Provides endpoints for paper-level actions that modify or remove data.
Separated from inspector (read-only detail view) for clarity.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.application.collection_service import CollectionAppService
from src.application.import_service import ImportAppService
from src.application.library_service import LibraryAppService
from src.domain.paper import PaperId
from src.web.app import (
    get_collection_service,
    get_import_service,
    get_library_service,
    get_templates,
    get_vault_path_from_state,
)
from src.web.helpers import to_vault_relative

logger = logging.getLogger(__name__)

router = APIRouter()
PDF_PICKER_SCRIPT = Path(__file__).resolve().parent.parent / "pdf_picker.py"
PDF_PICKER_TIMEOUT_SEC = 120


@router.post("/papers/{paper_id:path}/delete", response_class=HTMLResponse)
async def delete_paper(
    request: Request,
    paper_id: str,
) -> HTMLResponse:
    """Delete a paper completely: PDF, MD, assets folder, cache, and collection refs.

    Returns an htmx multi-swap response: refreshed paper list + empty inspector.
    Always succeeds from the user's perspective (idempotent for missing files).

    Args:
        paper_id: The paper's ID (URL-encoded, may contain slashes for DOI).

    Returns:
        HTML partial combining updated paper list and cleared inspector panel.
    """
    templates = get_templates()
    library_service: LibraryAppService = get_library_service(request)
    collection_service: CollectionAppService = get_collection_service(request)

    pid = PaperId(paper_id)

    # Remove from all collections first (cross-aggregate coordination)
    collection_service.remove_paper_from_all_collections(paper_id)

    # Delete the paper (files + cache)
    deleted = library_service.delete_paper(pid)
    if deleted:
        logger.info("Paper deleted via UI: %s", paper_id)
    else:
        logger.warning(
            "Paper not found for deletion (may already be removed): %s", paper_id
        )

    # Return refreshed paper list + empty inspector
    papers = library_service.list_all()

    return templates.TemplateResponse(
        request,
        "partials/delete_result.html",
        {
            "papers": papers,
        },
    )


@router.post(
    "/papers/{paper_id:path}/attach-pdf",
    response_class=HTMLResponse,
    response_model=None,
)
def attach_pdf(
    request: Request,
    paper_id: str,
) -> HTMLResponse | JSONResponse | Response:
    """Attach a selected PDF to an existing paper and return refreshed inspector."""
    try:
        result = subprocess.run(
            [sys.executable, str(PDF_PICKER_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=PDF_PICKER_TIMEOUT_SEC,
        )
        selected_path = result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("PDF picker timed out after %d seconds", PDF_PICKER_TIMEOUT_SEC)
        return JSONResponse({"error": "Timeout", "path": ""}, status_code=408)
    except Exception as exc:
        logger.error("PDF picker failed: %s", exc)
        return JSONResponse({"error": str(exc), "path": ""}, status_code=500)

    if not selected_path:
        return Response(status_code=204)

    templates = get_templates()
    import_service: ImportAppService = get_import_service(request)
    collection_service: CollectionAppService = get_collection_service(request)
    vault_path = get_vault_path_from_state(request)
    pid = PaperId(paper_id)
    paper = import_service.attach_pdf_to_paper(pid, selected_path)

    collections = collection_service.list_collections()
    collection_names = collection_service.list_collection_names_for_paper(paper.id.value)
    obsidian_note_path = to_vault_relative(paper.note_path, vault_path)
    obsidian_pdf_path = to_vault_relative(paper.pdf_path, vault_path)

    return templates.TemplateResponse(
        request,
        "partials/inspector.html",
        {
            "paper": paper,
            "collections": collections,
            "collection_names": collection_names,
            "obsidian_note_path": obsidian_note_path,
            "obsidian_pdf_path": obsidian_pdf_path,
        },
    )
