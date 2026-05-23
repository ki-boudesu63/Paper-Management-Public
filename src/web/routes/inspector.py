"""Inspector routes: paper detail view for the right panel.

Returns HTML partials for htmx to swap into the inspector panel.
Converts absolute note/pdf paths to vault-relative paths for Obsidian URIs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.application.collection_service import CollectionAppService
from src.application.library_service import LibraryAppService
from src.domain.paper import PaperId
from src.web.app import (
    get_collection_service,
    get_library_service,
    get_templates,
    get_vault_path_from_state,
)
from src.web.helpers import to_vault_relative

router = APIRouter()


@router.get("/inspector/{paper_id:path}", response_class=HTMLResponse)
async def inspector_detail(
    request: Request,
    paper_id: str,
) -> HTMLResponse:
    """Return inspector HTML partial for a specific paper.

    Converts absolute note_path / pdf_path to vault-relative POSIX paths
    so that the Obsidian ``file=`` parameter resolves correctly.

    Args:
        paper_id: The paper's ID (URL-encoded, may contain slashes for DOI).

    Returns:
        HTML partial with paper details, or empty state if not found.
    """
    templates = get_templates()
    service: LibraryAppService = get_library_service(request)
    collection_service: CollectionAppService = get_collection_service(request)
    vault_path = get_vault_path_from_state(request)

    pid = PaperId(paper_id)
    paper = service.get_by_id(pid)

    # Convert absolute paths to vault-relative for Obsidian URI compatibility
    obsidian_note_path: str | None = None
    obsidian_pdf_path: str | None = None
    if paper is not None:
        obsidian_note_path = to_vault_relative(paper.note_path, vault_path)
        if paper.has_pdf:
            obsidian_pdf_path = to_vault_relative(paper.pdf_path, vault_path)

    collections = collection_service.list_collections() if paper is not None else []
    collection_names = (
        collection_service.list_collection_names_for_paper(paper.id.value)
        if paper is not None
        else []
    )

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
