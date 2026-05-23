"""Import status routes: display import history and manual PDF import.

Shows success/duplicate/unsorted/error results from ImportAppService.
Provides a manual PDF import endpoint via file picker subprocess.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.application.import_service import ImportAppService
from src.web.app import get_import_service, get_templates

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to the standalone PDF file picker script
PDF_PICKER_SCRIPT = Path(__file__).resolve().parent.parent / "pdf_picker.py"

# Timeout for the PDF picker subprocess (seconds)
PDF_PICKER_TIMEOUT_SEC = 120


@router.get("/import", response_class=HTMLResponse)
async def import_status_page(request: Request) -> HTMLResponse:
    """Render the import status page with import history log."""
    templates = get_templates()
    service: ImportAppService = get_import_service(request)

    history = service.import_history
    # Reverse to show most recent first
    history_reversed = list(reversed(history))

    # Count by status
    status_counts = {
        "success": 0,
        "duplicate": 0,
        "unsorted": 0,
        "error": 0,
    }
    for result in history:
        if result.status in status_counts:
            status_counts[result.status] += 1

    # Check for result flash parameter from redirect
    result_flash = request.query_params.get("result", "")

    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "history": history_reversed,
            "status_counts": status_counts,
            "total_count": len(history),
            "result_flash": result_flash,
        },
    )


@router.post("/import/pick-pdf", response_model=None)
def pick_pdf(request: Request) -> RedirectResponse | JSONResponse:
    """Open a native PDF file selection dialog and import the selected file.

    Launches pdf_picker.py as a separate process to isolate tkinter GUI
    from the uvicorn server thread. If a file is selected, calls
    import_service.handle_new_pdf() and redirects to the import page
    with the result status.

    Returns:
        RedirectResponse on success/cancel, JSONResponse on error.
    """
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
        return JSONResponse(
            {"error": "Timeout", "path": ""},
            status_code=408,
        )
    except Exception as exc:
        logger.error("PDF picker failed: %s", exc)
        return JSONResponse(
            {"error": str(exc), "path": ""},
            status_code=500,
        )

    # User cancelled the dialog
    if not selected_path:
        return RedirectResponse(
            url="/import?cancelled=1",
            status_code=303,
        )

    # Execute import
    service: ImportAppService = get_import_service(request)
    import_result = service.handle_new_pdf(selected_path)

    return RedirectResponse(
        url=f"/import?result={import_result.status}",
        status_code=303,
    )
