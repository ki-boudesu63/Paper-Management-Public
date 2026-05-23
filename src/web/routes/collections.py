"""Collections routes: CRUD for paper collections.

Provides collection listing, creation, deletion, and detail views.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from src.application.collection_service import CollectionAppService
from src.web.app import get_collection_service, get_templates
from src.web.i18n import translate_for_request

router = APIRouter()


@router.get("/collections", response_class=HTMLResponse)
async def collections_page(request: Request) -> HTMLResponse:
    """Render the collections management page."""
    templates = get_templates()
    service: CollectionAppService = get_collection_service(request)

    collections = service.list_collections()

    return templates.TemplateResponse(
        request,
        "collections.html",
        {
            "collections": collections,
        },
    )


@router.post("/collections/create")
async def create_collection(
    request: Request,
    name: str = Form(...),
) -> RedirectResponse:
    """Create a new collection and redirect back to the list.

    Args:
        name: Display name for the new collection.

    Returns:
        Redirect to /collections.
    """
    service: CollectionAppService = get_collection_service(request)

    try:
        service.create_collection(name)
    except ValueError:
        pass  # Empty name; silently ignore

    return RedirectResponse(url="/collections", status_code=303)


@router.post("/collections/{collection_id}/delete")
async def delete_collection(
    request: Request,
    collection_id: str,
) -> RedirectResponse:
    """Delete a collection and redirect back to the list.

    Args:
        collection_id: The collection's ID string.

    Returns:
        Redirect to /collections.
    """
    service: CollectionAppService = get_collection_service(request)

    try:
        service.delete_collection(collection_id)
    except KeyError:
        pass  # Collection not found; silently ignore

    return RedirectResponse(url="/collections", status_code=303)


@router.get(
    "/collections/{collection_id}/papers",
    response_class=HTMLResponse,
)
async def collection_papers(
    request: Request,
    collection_id: str,
) -> HTMLResponse:
    """Render the papers inside a collection as an htmx partial."""
    templates = get_templates()
    service: CollectionAppService = get_collection_service(request)

    try:
        collection = service.get_collection(collection_id)
        papers = service.list_papers_in_collection(collection_id)
    except KeyError:
        collection = None
        papers = []

    return templates.TemplateResponse(
        request,
        "partials/collection_papers.html",
        {
            "collection": collection,
            "papers": papers,
        },
    )


@router.post(
    "/collections/{collection_id}/papers/{paper_id:path}/add",
)
async def add_paper_to_collection(
    request: Request,
    collection_id: str,
    paper_id: str,
) -> Response:
    """Add a paper to a collection and emit a toast event."""
    service: CollectionAppService = get_collection_service(request)

    try:
        service.add_paper_to_collection(collection_id, paper_id)
    except KeyError:
        payload = {
            "showToast": {
                "message": translate_for_request(
                    request,
                    "collections.add_error",
                ),
                "type": "error",
            }
        }
        return Response(
            status_code=404,
            headers={"HX-Trigger": json.dumps(payload)},
        )

    payload = {
        "showToast": {
            "message": translate_for_request(
                request,
                "collections.add_success",
            ),
            "type": "success",
        }
    }
    return Response(
        status_code=204,
        headers={"HX-Trigger": json.dumps(payload)},
    )


@router.post(
    "/collections/papers/{paper_id:path}/add",
)
async def add_paper_to_selected_collection(
    request: Request,
    paper_id: str,
    collection_id: str = Form(...),
) -> Response:
    """Add a paper to the collection selected in an inspector form."""
    return await add_paper_to_collection(
        request=request,
        collection_id=collection_id,
        paper_id=paper_id,
    )


@router.post(
    "/collections/{collection_id}/papers/{paper_id:path}/remove",
    response_class=HTMLResponse,
)
async def remove_paper_from_collection(
    request: Request,
    collection_id: str,
    paper_id: str,
) -> HTMLResponse:
    """Remove a paper from a collection and return the updated list partial."""
    templates = get_templates()
    service: CollectionAppService = get_collection_service(request)

    collection = service.get_collection(collection_id)
    if collection is not None:
        try:
            collection = service.remove_paper_from_collection(collection_id, paper_id)
        except ValueError:
            pass

    papers = []
    if collection is not None:
        papers = service.list_papers_in_collection(collection_id)

    return templates.TemplateResponse(
        request,
        "partials/collection_papers.html",
        {
            "collection": collection,
            "papers": papers,
        },
    )
