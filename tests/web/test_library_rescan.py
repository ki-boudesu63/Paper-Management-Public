"""Tests for library rescan button and endpoint.

Verifies:
- POST /library/rescan returns 200 with paper list partial
- rescan() is called on LibraryAppService
- HX-Trigger header fires showToast event
- library.html contains the rescan button with correct htmx attributes
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestLibraryRescanEndpoint:
    """Tests for POST /library/rescan endpoint."""

    def test_rescan_returns_200(self, client: TestClient) -> None:
        """Rescan endpoint returns HTTP 200."""
        response = client.post("/library/rescan")
        assert response.status_code == 200

    def test_rescan_calls_service_rescan(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan endpoint delegates to LibraryAppService.rescan()."""
        mock_library_service.rescan.return_value = 3
        client.post("/library/rescan")
        mock_library_service.rescan.assert_called_once()

    def test_rescan_returns_paper_list_partial(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan endpoint returns the paper list partial HTML."""
        mock_library_service.rescan.return_value = 3
        response = client.post("/library/rescan")
        content = response.text
        # The paper list partial should contain paper items or empty state
        assert "paper-list__item" in content or "empty-state" in content

    def test_rescan_returns_html_content_type(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan endpoint returns text/html content type."""
        mock_library_service.rescan.return_value = 3
        response = client.post("/library/rescan")
        assert "text/html" in response.headers["content-type"]

    def test_rescan_triggers_show_toast(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan endpoint sends HX-Trigger header with showToast event."""
        mock_library_service.rescan.return_value = 3
        response = client.post("/library/rescan")
        hx_trigger = response.headers.get("hx-trigger")
        assert hx_trigger is not None
        assert "showToast" in hx_trigger

    def test_rescan_toast_contains_message(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan toast includes a message string."""
        import json

        mock_library_service.rescan.return_value = 5
        response = client.post("/library/rescan")
        hx_trigger = response.headers.get("hx-trigger", "")
        trigger_data = json.loads(hx_trigger)
        assert "message" in trigger_data["showToast"]

    def test_rescan_refreshes_paper_list(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """After rescan, list_all is called to get fresh paper list."""
        mock_library_service.rescan.return_value = 3
        client.post("/library/rescan")
        mock_library_service.list_all.assert_called()


class TestLibraryRescanButton:
    """Tests for rescan button presence in library.html."""

    def test_library_page_has_rescan_button(
        self,
        client: TestClient,
    ) -> None:
        """Library page contains a rescan button."""
        response = client.get("/")
        content = response.text
        assert 'id="rescan-btn"' in content

    def test_rescan_button_has_hx_post(
        self,
        client: TestClient,
    ) -> None:
        """Rescan button has hx-post pointing to /library/rescan."""
        response = client.get("/")
        content = response.text
        assert 'hx-post="/library/rescan"' in content

    def test_rescan_button_targets_paper_list(
        self,
        client: TestClient,
    ) -> None:
        """Rescan button targets #paper-list for htmx swap."""
        response = client.get("/")
        content = response.text
        assert 'hx-target="#paper-list"' in content

    def test_rescan_button_has_title(
        self,
        client: TestClient,
    ) -> None:
        """Rescan button has a descriptive title attribute."""
        response = client.get("/")
        content = response.text
        assert 'title="ライブラリを再スキャン"' in content
