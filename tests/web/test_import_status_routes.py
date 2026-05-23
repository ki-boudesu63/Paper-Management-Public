"""Tests for import status routes.

Uses FastAPI TestClient with mocked ImportAppService.
No real filesystem or network access.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

# ============================================================
# Import status page (GET /import)
# ============================================================


class TestImportStatusPage:
    """Tests for the import status page."""

    def test_import_page_returns_200(self, client: TestClient) -> None:
        """GET /import returns 200 OK."""
        response = client.get("/import")
        assert response.status_code == 200

    def test_import_page_contains_heading(self, client: TestClient) -> None:
        """GET /import renders the page heading."""
        response = client.get("/import")
        assert response.status_code == 200
        assert "取り込み状況" in response.text

    def test_import_page_shows_status_counts(
        self, client: TestClient
    ) -> None:
        """GET /import displays status summary counts."""
        response = client.get("/import")
        assert response.status_code == 200
        # Sample history has 3 items total
        assert "合計:" in response.text

    def test_import_page_shows_success_badge(
        self, client: TestClient
    ) -> None:
        """GET /import shows success status badge."""
        response = client.get("/import")
        assert "status-badge--success" in response.text

    def test_import_page_shows_unsorted_badge(
        self, client: TestClient
    ) -> None:
        """GET /import shows unsorted status badge."""
        response = client.get("/import")
        assert "status-badge--unsorted" in response.text

    def test_import_page_shows_error_badge(
        self, client: TestClient
    ) -> None:
        """GET /import shows error status badge."""
        response = client.get("/import")
        assert "status-badge--error" in response.text

    def test_import_page_shows_file_paths(
        self, client: TestClient
    ) -> None:
        """GET /import displays file paths in the log."""
        response = client.get("/import")
        assert "paper1.pdf" in response.text

    def test_import_page_empty_history(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """GET /import with no history shows empty state."""
        mock_import_service.import_history = []

        response = client.get("/import")
        assert response.status_code == 200
        assert "取り込み履歴がありません" in response.text

    def test_import_page_has_nav_links(self, client: TestClient) -> None:
        """GET /import has navigation links to other pages."""
        response = client.get("/import")
        assert 'href="/"' in response.text
        assert 'href="/collections"' in response.text
        assert 'href="/settings"' in response.text

    def test_import_page_renders_import_log_table(
        self, client: TestClient
    ) -> None:
        """GET /import renders the import log table structure."""
        response = client.get("/import")
        assert "import-log-table" in response.text
