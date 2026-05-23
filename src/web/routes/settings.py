"""Settings routes: configuration management for paths and vault.

Provides the settings page to edit library_root, vault_path,
style_folder, watch_folder, vault_name, and contact_email.
Also provides a folder picker endpoint that launches a native
tkinter dialog via subprocess for safe GUI isolation.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.application.library_service import LibraryAppService
from src.config.settings import load_settings, save_settings, set_language
from src.web.app import get_config_path, get_library_service, get_templates

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to the standalone folder picker script
FOLDER_PICKER_SCRIPT = Path(__file__).resolve().parent.parent / "folder_picker.py"

# Timeout for the folder picker subprocess (seconds)
FOLDER_PICKER_TIMEOUT_SEC = 120


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Render the settings page with current configuration values."""
    templates = get_templates()
    config_path = get_config_path(request)

    settings = load_settings(config_path)
    paths = settings.get("paths", {})

    # Path existence checks
    path_status: dict[str, bool] = {}
    for key in ("library_root", "vault_path", "style_folder", "watch_folder"):
        val = paths.get(key, "")
        path_status[key] = bool(val and Path(val).exists())

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "paths": paths,
            "vault_name": settings.get("vault_name", ""),
            "contact_email": settings.get("import_settings", {}).get(
                "contact_email", ""
            ),
            "path_status": path_status,
            "saved": request.query_params.get("saved") == "1",
            "rescanned": request.query_params.get("rescanned") == "1",
        },
    )


@router.post("/settings/save")
async def save_settings_form(
    request: Request,
    library_root: str = Form(default=""),
    vault_path: str = Form(default=""),
    style_folder: str = Form(default=""),
    watch_folder: str = Form(default=""),
    vault_name: str = Form(default=""),
    contact_email: str = Form(default=""),
    language: str = Form(default="ja"),
) -> RedirectResponse:
    """Save settings from the form and redirect back with success flag.

    Merges form values into the existing config to preserve
    keys not exposed in the UI (e.g., server settings).
    """
    config_path = get_config_path(request)
    settings = load_settings(config_path)

    # Merge path values
    if "paths" not in settings:
        settings["paths"] = {}
    settings["paths"]["library_root"] = library_root
    settings["paths"]["vault_path"] = vault_path
    settings["paths"]["style_folder"] = style_folder
    settings["paths"]["watch_folder"] = watch_folder

    # Merge vault_name
    settings["vault_name"] = vault_name

    # Merge contact_email
    if "import_settings" not in settings:
        settings["import_settings"] = {}
    settings["import_settings"]["contact_email"] = contact_email

    save_settings(settings, config_path)
    set_language(language, config_path)

    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.post("/settings/pick-folder")
async def pick_folder() -> JSONResponse:
    """Open a native folder selection dialog via subprocess.

    Launches folder_picker.py as a separate process to isolate
    tkinter GUI from the uvicorn server thread. Returns the
    selected path or an empty string if cancelled.
    """

    try:
        result = subprocess.run(
            [sys.executable, str(FOLDER_PICKER_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=FOLDER_PICKER_TIMEOUT_SEC,
        )
        selected_path = result.stdout.strip()
        return JSONResponse({"path": selected_path})
    except subprocess.TimeoutExpired:
        logger.warning(
            "Folder picker timed out after %d seconds", FOLDER_PICKER_TIMEOUT_SEC
        )
        return JSONResponse({"path": "", "error": "Timeout"}, status_code=408)
    except Exception as exc:
        logger.error("Folder picker failed: %s", exc)
        return JSONResponse({"path": "", "error": str(exc)}, status_code=500)


@router.post("/settings/rescan")
async def rescan_library(request: Request) -> RedirectResponse:
    """Trigger a full rescan of the paper library.

    Calls PaperRepository.scan() via LibraryAppService to rebuild the
    in-memory cache from the filesystem. Redirects back to settings
    with a success flag, following the same pattern as save_settings_form.
    """
    library_service: LibraryAppService = get_library_service(request)
    paper_count = library_service.rescan()
    logger.info("Library rescan triggered from settings: %d papers found", paper_count)
    return RedirectResponse(url="/settings?rescanned=1", status_code=303)
