"""FastAPI application factory with dependency injection.

Builds the app, wires up repositories and application services,
and triggers the initial scan on startup.
Integrates FolderWatcher for automatic PDF import on startup.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.adapters.filesystem.collection_repository import (
    FilesystemCollectionRepository,
)
from src.adapters.filesystem.paper_repository import FilesystemPaperRepository
from src.adapters.watcher import FolderWatcher
from src.application.collection_service import CollectionAppService
from src.application.import_service import ImportAppService
from src.application.library_service import LibraryAppService
from src.application.metadata_buffer import MetadataBuffer
from src.config.settings import get_vault_name, load_settings

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Valid initial letters for the rail
INITIAL_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["#"]


# ============================================================
# Thread-safe callback helper
# ============================================================


def _make_threadsafe_callback(
    import_service: ImportAppService,
    lock: threading.Lock,
) -> Callable[[str], None]:
    """Create a thread-safe callback for the FolderWatcher.

    The watcher fires callbacks from a background thread. This wrapper
    serializes access to import_service.handle_new_pdf via a lock to
    protect shared state (import_history, paper_repo cache).

    Args:
        import_service: The import service to delegate to.
        lock: A threading.Lock to serialize access.

    Returns:
        A callback function compatible with FolderWatcher.on_new_pdf.
    """

    def _callback(pdf_path: str) -> None:
        with lock:
            import_service.handle_new_pdf(pdf_path)

    return _callback


# ============================================================
# Application state container
# ============================================================


class AppState:
    """Holds application-wide services and configuration."""

    library_service: LibraryAppService
    collection_service: CollectionAppService
    import_service: ImportAppService
    vault_name: str
    vault_path: str
    library_root: str
    config_path: str


# ============================================================
# Lifespan
# ============================================================


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: build DI graph, scan paper repository, start watcher."""
    settings = load_settings()
    paths = settings.get("paths", {})

    library_root_str = paths.get("library_root", "")
    vault_path_str = paths.get("vault_path", "")

    # Build repositories
    if library_root_str and Path(library_root_str).exists():
        paper_repo = FilesystemPaperRepository(Path(library_root_str))
        paper_repo.scan()
        logger.info(
            "Paper repository scanned: %d papers loaded",
            len(paper_repo.find_all()),
        )
    else:
        # Create a stub repository for development/testing
        paper_repo = _create_stub_paper_repo()

    collection_repo_path = Path(library_root_str) if library_root_str else None
    if collection_repo_path and collection_repo_path.exists():
        collection_repo = FilesystemCollectionRepository(collection_repo_path)
    else:
        collection_repo = _create_stub_collection_repo()

    # Build application services
    library_service = LibraryAppService(paper_repo)
    collection_service = CollectionAppService(collection_repo, paper_repo)

    # ImportAppService with real DI (Phase 5):
    # CrossRefClient as MetadataResolver + MetadataBuffer for extension integration
    import_settings = settings.get("import_settings", {})
    contact_email = import_settings.get("contact_email", "")
    unsorted_folder_name = import_settings.get("unsorted_folder_name", "未整理")

    # Modification A: Wire extract_full_text from config
    extract_full_text = bool(import_settings.get("extract_full_text", False))

    from src.adapters.crossref_client import CrossRefMetadataResolver

    metadata_resolver = CrossRefMetadataResolver(contact_email=contact_email)
    metadata_buffer = MetadataBuffer()
    library_root_path = Path(library_root_str) if library_root_str else _get_tmp_path()

    import_service = ImportAppService(
        paper_repo=paper_repo,
        metadata_resolver=metadata_resolver,
        metadata_buffer=metadata_buffer,
        library_root=library_root_path,
        unsorted_folder_name=unsorted_folder_name,
        extract_full_text=extract_full_text,
    )

    # Store in app state
    state = application.state
    state.library_service = library_service
    state.collection_service = collection_service
    state.import_service = import_service
    state.vault_name = get_vault_name()
    state.vault_path = vault_path_str
    state.library_root = library_root_str
    state.config_path = ""  # Use default config path resolution

    # Modification B: Start FolderWatcher if watch_folder is configured
    watcher = None
    watch_folder_str = paths.get("watch_folder", "")
    if watch_folder_str and Path(watch_folder_str).exists():
        try:
            import_lock = threading.Lock()
            callback = _make_threadsafe_callback(import_service, import_lock)
            watcher = FolderWatcher(
                watch_folder=Path(watch_folder_str),
                on_new_pdf=callback,
            )
            watcher.start()
            state.folder_watcher = watcher
            logger.info("FolderWatcher started for: %s", watch_folder_str)
        except Exception:
            logger.warning(
                "Failed to start FolderWatcher for: %s",
                watch_folder_str,
                exc_info=True,
            )
            watcher = None
    else:
        if watch_folder_str:
            logger.warning(
                "Watch folder does not exist, skipping watcher: %s",
                watch_folder_str,
            )
        else:
            logger.info("No watch folder configured, skipping watcher")

    logger.info("Application started successfully")
    yield

    # Shutdown: stop watcher if running
    if watcher is not None:
        try:
            watcher.stop()
            logger.info("FolderWatcher stopped")
        except Exception:
            logger.warning("Error stopping FolderWatcher", exc_info=True)

    logger.info("Application shutting down")


def _create_stub_paper_repo() -> FilesystemPaperRepository:
    """Create a temporary paper repo for when library_root is not configured."""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="paper_mgmt_"))
    repo = FilesystemPaperRepository(tmp)
    repo.scan()
    return repo


def _create_stub_collection_repo() -> FilesystemCollectionRepository:
    """Create a temporary collection repo for when library_root is not configured."""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="paper_mgmt_coll_"))
    return FilesystemCollectionRepository(tmp)


def _get_tmp_path() -> Path:
    """Create a temporary directory for when library_root is not configured."""
    import tempfile

    return Path(tempfile.mkdtemp(prefix="paper_mgmt_import_"))


# ============================================================
# App factory
# ============================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from fastapi.middleware.cors import CORSMiddleware

    application = FastAPI(
        title="Paper Management",
        description="Reading Room - academic paper management UI",
        lifespan=lifespan,
    )

    # CORS middleware for Chrome extension and localhost requests.
    # Note: Chrome extension origins (chrome-extension://<id>) must be matched
    # via allow_origin_regex -- Starlette does NOT expand "chrome-extension://*"
    # wildcards in allow_origins, which previously caused 400 on the CORS
    # preflight (OPTIONS) request.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1",
            "http://localhost",
            "http://127.0.0.1:12000",
            "http://localhost:12000",
        ],
        allow_origin_regex=r"chrome-extension://.*",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Static files
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    # Register routes
    from src.web.routes.api import router as api_router
    from src.web.routes.collections import router as collections_router
    from src.web.routes.import_status import router as import_status_router
    from src.web.routes.inspector import router as inspector_router
    from src.web.routes.library import router as library_router
    from src.web.routes.paper_actions import router as paper_actions_router
    from src.web.routes.settings import router as settings_router

    application.include_router(api_router)
    application.include_router(library_router)
    application.include_router(inspector_router)
    application.include_router(paper_actions_router)
    application.include_router(import_status_router)
    application.include_router(collections_router)
    application.include_router(settings_router)

    return application


# ============================================================
# Dependency helpers
# ============================================================


def get_templates() -> Jinja2Templates:
    """Return configured Jinja2 templates instance."""
    from src.web.i18n import configure_templates_globals

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    configure_templates_globals(templates.env.globals)
    return templates


def get_library_service(request: Request) -> LibraryAppService:
    """Extract LibraryAppService from app state."""
    return request.app.state.library_service


def get_collection_service(request: Request) -> CollectionAppService:
    """Extract CollectionAppService from app state."""
    return request.app.state.collection_service


def get_import_service(request: Request) -> ImportAppService:
    """Extract ImportAppService from app state."""
    return request.app.state.import_service


def get_vault_name_from_state(request: Request) -> str:
    """Extract vault name from app state."""
    return request.app.state.vault_name


def get_vault_path_from_state(request: Request) -> str:
    """Extract vault path from app state."""
    return request.app.state.vault_path


def get_config_path(request: Request) -> str | None:
    """Extract config path from app state.

    Returns None to use default config path resolution when empty.
    """
    path = request.app.state.config_path
    return path if path else None


# Module-level app instance for uvicorn
app = create_app()
