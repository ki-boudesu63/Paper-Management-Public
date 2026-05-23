"""Shared fixtures for web layer tests.

Provides a FastAPI TestClient with mocked application services,
isolating tests from the filesystem and real data.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from src.application.collection_service import CollectionAppService
from src.application.import_service import ImportAppService, ImportResult
from src.application.library_service import LibraryAppService
from src.domain.paper import (
    DOI,
    Author,
    InitialLetter,
    Metadata,
    Paper,
    PaperId,
    PublicationYear,
)
from src.web.app import STATIC_DIR

# ============================================================
# Sample data factories
# ============================================================


def make_paper(
    paper_id: str = "10.1234/test.001",
    title: str = "Test Paper on Tracheal Regeneration",
    family: str = "Kitano",
    given: str = "Takahiro",
    year: int = 2024,
    doi_value: str = "10.1234/test.001",
    tags: list[str] | None = None,
    pdf_path: str = "/papers/K/Kitano 2024 - Test.pdf",
    note_path: str | None = "/papers/K/Kitano 2024 - Test.md",
) -> Paper:
    """Create a sample Paper for testing."""
    doi = DOI(doi_value) if doi_value else None
    metadata = Metadata(
        title=title,
        authors=(Author(family_name=family, given_name=given),),
        year=PublicationYear(year),
        doi=doi,
    )
    return Paper(
        id=PaperId(paper_id),
        metadata=metadata,
        pdf_path=pdf_path,
        note_path=note_path,
        initial_letter=InitialLetter.from_family_name(family),
        tags=tags or [],
    )


SAMPLE_PAPERS = [
    make_paper(),
    make_paper(
        paper_id="10.5678/test.002",
        title="Stem Cell Differentiation Study",
        family="Mizuno",
        given="Yuki",
        year=2023,
        doi_value="10.5678/test.002",
        pdf_path="/papers/M/Mizuno 2023 - Stem.pdf",
        note_path="/papers/M/Mizuno 2023 - Stem.md",
    ),
    make_paper(
        paper_id="10.9999/test.003",
        title="Advanced Biomaterials Review",
        family="Anderson",
        given="James",
        year=2025,
        doi_value="10.9999/test.003",
        pdf_path="/papers/A/Anderson 2025 - Advanced.pdf",
        note_path="/papers/A/Anderson 2025 - Advanced.md",
    ),
]

SAMPLE_IMPORT_HISTORY: list[ImportResult] = [
    ImportResult(
        pdf_path="/downloads/paper1.pdf",
        status="success",
        paper=SAMPLE_PAPERS[0],
    ),
    ImportResult(
        pdf_path="/downloads/paper2.pdf",
        status="unsorted",
        message="Metadata resolution failed. Moved to: /papers/未整理/paper2.pdf",
    ),
    ImportResult(
        pdf_path="/downloads/paper3.pdf",
        status="error",
        message="PDF file does not exist",
    ),
]


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture()
def mock_library_service() -> MagicMock:
    """Create a mock LibraryAppService with sample data."""
    service = MagicMock(spec=LibraryAppService)
    service.list_all.return_value = SAMPLE_PAPERS
    service.list_by_initial.return_value = []
    service.search.return_value = []
    service.get_by_id.return_value = None
    return service


@pytest.fixture()
def mock_collection_service() -> MagicMock:
    """Create a mock CollectionAppService."""
    service = MagicMock(spec=CollectionAppService)
    service.list_collections.return_value = []
    service.list_collection_names_for_paper.return_value = []
    return service


@pytest.fixture()
def mock_import_service() -> MagicMock:
    """Create a mock ImportAppService with sample import history."""
    service = MagicMock(spec=ImportAppService)
    service.import_history = SAMPLE_IMPORT_HISTORY
    return service


@pytest.fixture()
def test_config_path(tmp_path: Path) -> Path:
    """Create a temporary config.yaml for settings tests."""
    import yaml

    config = {
        "paths": {
            "library_root": "",
            "vault_path": "",
            "style_folder": "",
            "watch_folder": "",
        },
        "vault_name": "TestVault",
        "server": {"host": "127.0.0.1", "port": 12000},
        "import_settings": {
            "unsorted_folder_name": "未整理",
            "watch_interval_sec": 2,
            "contact_email": "test@example.com",
        },
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    return config_file


@pytest.fixture()
def client(
    mock_library_service: MagicMock,
    mock_collection_service: MagicMock,
    mock_import_service: MagicMock,
    test_config_path: Path,
) -> Generator[TestClient, None, None]:
    """Create a FastAPI TestClient with mocked services.

    Creates a fresh app without lifespan to avoid filesystem access.
    Injects mocked services directly into app state.
    """

    @asynccontextmanager
    async def _noop_lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        """No-op lifespan for testing."""
        yield

    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(lifespan=_noop_lifespan)

    # CORS middleware (mirrors create_app in src/web/app.py)
    # Note: Chrome extension origins must use allow_origin_regex,
    # not allow_origins with wildcards (Starlette does not expand them).
    app.add_middleware(
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

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Register all routes
    from src.web.routes.api import router as api_router
    from src.web.routes.collections import router as collections_router
    from src.web.routes.import_status import router as import_status_router
    from src.web.routes.inspector import router as inspector_router
    from src.web.routes.library import router as library_router
    from src.web.routes.paper_actions import router as paper_actions_router
    from src.web.routes.settings import router as settings_router

    app.include_router(api_router)
    app.include_router(library_router)
    app.include_router(inspector_router)
    app.include_router(paper_actions_router)
    app.include_router(import_status_router)
    app.include_router(collections_router)
    app.include_router(settings_router)

    # Inject mocked services into app state
    app.state.library_service = mock_library_service
    app.state.collection_service = mock_collection_service
    app.state.import_service = mock_import_service
    app.state.vault_name = "TestVault"
    app.state.vault_path = "G:/TestVault"
    app.state.library_root = "G:/Papers"
    app.state.config_path = str(test_config_path)

    with TestClient(app, raise_server_exceptions=True) as tc:
        yield tc
