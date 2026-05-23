"""Library routes: paper listing, search, initial-letter filtering, obsidian URI.

Serves the main library page and htmx partials for the paper list.
Also provides a rescan endpoint for rebuilding the paper cache from
the library toolbar.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from src.application.library_service import SearchQuery
from src.domain.paper import Paper
from src.web.app import (
    INITIAL_LETTERS,
    get_library_service,
    get_templates,
    get_vault_name_from_state,
)
from src.web.i18n import translate_for_request

router = APIRouter()

logger = logging.getLogger(__name__)


# ============================================================
# Helpers
# ============================================================


def _build_letter_counts(papers: list[Paper]) -> dict[str, int]:
    """Count papers per initial letter."""
    counts: dict[str, int] = {letter: 0 for letter in INITIAL_LETTERS}
    for paper in papers:
        letter = paper.initial_letter.letter
        if letter in counts:
            counts[letter] += 1
    return counts


def _build_obsidian_open_uri(
    vault_name: str,
    file_path: str,
) -> str:
    """Build obsidian://open URI for a file.

    Args:
        vault_name: Obsidian vault name.
        file_path: Relative path within the vault.

    Returns:
        obsidian:// URI string.
    """
    encoded_vault = quote(vault_name, safe="")
    encoded_path = quote(file_path, safe="/")
    return f"obsidian://open?vault={encoded_vault}&file={encoded_path}"


def _build_obsidian_search_uri(
    vault_name: str,
    query_text: str,
) -> str:
    """Build obsidian://search URI.

    Args:
        vault_name: Obsidian vault name.
        query_text: Search query text.

    Returns:
        obsidian:// URI string.
    """
    encoded_vault = quote(vault_name, safe="")
    encoded_query = quote(query_text, safe="")
    return f"obsidian://search?vault={encoded_vault}&query={encoded_query}"


# ============================================================
# Routes
# ============================================================


@router.get("/", response_class=HTMLResponse)
async def library_page(
    request: Request,
    letter: str = Query(default=""),
    q: str = Query(default=""),
    author: str = Query(default=""),
    year: int | None = Query(default=None),
    tag: str = Query(default=""),
) -> HTMLResponse:
    """Render the main library page with 3-column layout."""
    templates = get_templates()
    service = get_library_service(request)
    vault_name = get_vault_name_from_state(request)

    # Get all papers for letter counts
    all_papers = service.list_all()
    letter_counts = _build_letter_counts(all_papers)

    # Apply filters
    if q:
        # Cross-field free-text AND search (author/title/abstract/memo/year/tag)
        papers = service.fulltext_search(q)
    elif author or year or tag:
        papers = service.search(SearchQuery(author=author, year=year, tag=tag))
    elif letter:
        papers = service.list_by_initial(letter)
    else:
        papers = all_papers

    active_letter = letter.upper() if letter else ""

    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "papers": papers,
            "initial_letters": INITIAL_LETTERS,
            "active_letter": active_letter,
            "letter_counts": letter_counts,
            "vault_name": vault_name,
            "search_query": q,
            "search_author": author,
            "search_year": year,
            "search_tag": tag,
        },
    )


@router.get("/papers", response_class=HTMLResponse)
async def paper_list_partial(
    request: Request,
    letter: str = Query(default=""),
    q: str = Query(default=""),
    author: str = Query(default=""),
    year: int | None = Query(default=None),
    tag: str = Query(default=""),
) -> HTMLResponse:
    """Return paper list HTML partial (for htmx swaps)."""
    templates = get_templates()
    service = get_library_service(request)

    if q:
        # Cross-field free-text AND search (author/title/abstract/memo/year/tag)
        papers = service.fulltext_search(q)
    elif author or year or tag:
        papers = service.search(SearchQuery(author=author, year=year, tag=tag))
    elif letter:
        papers = service.list_by_initial(letter)
    else:
        papers = service.list_all()

    return templates.TemplateResponse(
        request,
        "partials/paper_list.html",
        {
            "papers": papers,
        },
    )


@router.post("/library/rescan", response_class=HTMLResponse)
async def rescan_from_library(request: Request) -> HTMLResponse:
    """Rescan the paper library and return a refreshed paper list partial.

    Called from the toolbar rescan button via htmx. Triggers
    LibraryAppService.rescan() to rebuild the in-memory cache,
    then returns the paper_list.html partial for htmx swap into
    #paper-list. Sends an HX-Trigger header to fire the showToast
    event on the client.
    """
    templates = get_templates()
    service = get_library_service(request)

    paper_count = service.rescan()
    logger.info("Library rescan triggered from toolbar: %d papers found", paper_count)

    # Fetch refreshed paper list
    papers = service.list_all()

    # Build the HX-Trigger payload for toast notification
    toast_payload = json.dumps(
        {
            "showToast": {
                "message": translate_for_request(
                    request,
                    "library.rescan_done",
                    count=paper_count,
                ),
                "type": "success",
            }
        }
    )

    response = templates.TemplateResponse(
        request,
        "partials/paper_list.html",
        {
            "papers": papers,
        },
    )
    response.headers["HX-Trigger"] = toast_payload
    return response


@router.get("/api/obsidian/open")
async def obsidian_open_uri(
    request: Request,
    file_path: str = Query(..., alias="file"),
) -> dict[str, str]:
    """Generate obsidian://open URI for a file.

    Args:
        file_path: Relative path within the vault.

    Returns:
        JSON with the obsidian URI.
    """
    vault_name = get_vault_name_from_state(request)
    uri = _build_obsidian_open_uri(vault_name, file_path)
    return {"uri": uri}


@router.get("/api/obsidian/search")
async def obsidian_search_uri(
    request: Request,
    q: str = Query(...),
) -> dict[str, str]:
    """Generate obsidian://search URI.

    Args:
        q: Search query text.

    Returns:
        JSON with the obsidian URI.
    """
    vault_name = get_vault_name_from_state(request)
    uri = _build_obsidian_search_uri(vault_name, q)
    return {"uri": uri}
