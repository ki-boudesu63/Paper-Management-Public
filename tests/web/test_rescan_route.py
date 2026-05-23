"""Tests for the rescan route (POST /settings/rescan).

Uses the shared TestClient fixture with mocked services.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestRescanRoute:
    """Tests for POST /settings/rescan."""

    def test_rescan_returns_redirect(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan should redirect to settings page with rescanned flag."""
        mock_library_service.rescan.return_value = 5

        response = client.post("/settings/rescan", follow_redirects=False)

        assert response.status_code == 303
        assert "/settings?rescanned=1" in response.headers["location"]

    def test_rescan_calls_service_rescan(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Rescan endpoint should call library_service.rescan."""
        mock_library_service.rescan.return_value = 10

        client.post("/settings/rescan", follow_redirects=False)

        mock_library_service.rescan.assert_called_once()

    def test_rescan_followed_by_settings_page_shows_message(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """After rescan redirect, settings page shows success message."""
        mock_library_service.rescan.return_value = 3

        response = client.get("/settings?rescanned=1")

        assert response.status_code == 200
        assert "ライブラリを再スキャンしました" in response.text

    def test_settings_page_without_rescanned_flag(
        self,
        client: TestClient,
    ) -> None:
        """Settings page without rescanned flag should not show rescan message."""
        response = client.get("/settings")

        assert response.status_code == 200
        assert "ライブラリを再スキャンしました" not in response.text
