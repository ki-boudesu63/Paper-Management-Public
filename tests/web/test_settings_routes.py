"""Tests for settings routes.

Uses FastAPI TestClient with a temporary config.yaml file.
No real filesystem or network access beyond the temp config.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from fastapi.testclient import TestClient

# ============================================================
# Settings page (GET /settings)
# ============================================================


class TestSettingsPage:
    """Tests for the settings page."""

    def test_settings_page_returns_200(self, client: TestClient) -> None:
        """GET /settings returns 200 OK."""
        response = client.get("/settings")
        assert response.status_code == 200

    def test_settings_page_contains_heading(
        self, client: TestClient
    ) -> None:
        """GET /settings renders the page heading."""
        response = client.get("/settings")
        assert "設定" in response.text

    def test_settings_page_shows_path_fields(
        self, client: TestClient
    ) -> None:
        """GET /settings includes all 4 path input fields."""
        response = client.get("/settings")
        assert 'id="library_root"' in response.text
        assert 'id="vault_path"' in response.text
        assert 'id="style_folder"' in response.text
        assert 'id="watch_folder"' in response.text

    def test_settings_page_shows_vault_name(
        self, client: TestClient
    ) -> None:
        """GET /settings includes vault name field."""
        response = client.get("/settings")
        assert 'id="vault_name"' in response.text

    def test_settings_page_shows_contact_email(
        self, client: TestClient
    ) -> None:
        """GET /settings includes contact email field."""
        response = client.get("/settings")
        assert 'id="contact_email"' in response.text

    def test_settings_page_has_save_button(
        self, client: TestClient
    ) -> None:
        """GET /settings includes the save button."""
        response = client.get("/settings")
        assert "設定を保存" in response.text

    def test_settings_page_has_nav_links(
        self, client: TestClient
    ) -> None:
        """GET /settings has navigation links to other pages."""
        response = client.get("/settings")
        assert 'href="/"' in response.text
        assert 'href="/import"' in response.text
        assert 'href="/collections"' in response.text

    def test_settings_page_shows_current_values(
        self, client: TestClient
    ) -> None:
        """GET /settings shows current config values in inputs."""
        response = client.get("/settings")
        # The test config has vault_name="TestVault"
        assert "TestVault" in response.text
        # The test config has contact_email="test@example.com"
        assert "test@example.com" in response.text


# ============================================================
# Save settings (POST /settings/save)
# ============================================================


class TestSaveSettings:
    """Tests for saving settings."""

    def test_save_settings_redirects(self, client: TestClient) -> None:
        """POST /settings/save redirects to /settings?saved=1."""
        response = client.post(
            "/settings/save",
            data={
                "library_root": "D:/Papers",
                "vault_path": "G:/Vault",
                "style_folder": "",
                "watch_folder": "",
                "vault_name": "MyVault",
                "contact_email": "me@test.com",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/settings?saved=1"

    def test_save_settings_persists_values(
        self,
        client: TestClient,
        test_config_path: Path,
    ) -> None:
        """POST /settings/save writes values to config.yaml."""
        client.post(
            "/settings/save",
            data={
                "library_root": "D:/NewPapers",
                "vault_path": "G:/NewVault",
                "style_folder": "D:/Styles",
                "watch_folder": "C:/Downloads",
                "vault_name": "UpdatedVault",
                "contact_email": "updated@test.com",
            },
            follow_redirects=False,
        )

        # Verify the config file was updated
        with open(test_config_path, encoding="utf-8") as f:
            saved = yaml.safe_load(f)

        assert saved["paths"]["library_root"] == "D:/NewPapers"
        assert saved["paths"]["vault_path"] == "G:/NewVault"
        assert saved["paths"]["style_folder"] == "D:/Styles"
        assert saved["paths"]["watch_folder"] == "C:/Downloads"
        assert saved["vault_name"] == "UpdatedVault"
        assert saved["import_settings"]["contact_email"] == "updated@test.com"

    def test_save_settings_preserves_server_config(
        self,
        client: TestClient,
        test_config_path: Path,
    ) -> None:
        """POST /settings/save does not overwrite server settings."""
        client.post(
            "/settings/save",
            data={
                "library_root": "",
                "vault_path": "",
                "style_folder": "",
                "watch_folder": "",
                "vault_name": "",
                "contact_email": "",
            },
            follow_redirects=False,
        )

        with open(test_config_path, encoding="utf-8") as f:
            saved = yaml.safe_load(f)

        # Server config should be preserved from original
        assert saved["server"]["host"] == "127.0.0.1"
        assert saved["server"]["port"] == 12000

    def test_saved_flag_shows_toast(self, client: TestClient) -> None:
        """GET /settings?saved=1 shows a success toast."""
        response = client.get("/settings?saved=1")
        assert response.status_code == 200
        assert "設定を保存しました" in response.text


# ============================================================
# Folder picker (POST /settings/pick-folder)
# ============================================================


class TestFolderPicker:
    """Tests for the folder picker endpoint."""

    @patch("src.web.routes.settings.subprocess.run")
    def test_pick_folder_returns_selected_path(
        self, mock_run: MagicMock, client: TestClient
    ) -> None:
        """POST /settings/pick-folder returns the selected folder path."""
        mock_run.return_value = MagicMock(stdout="D:/Papers\n", returncode=0)
        response = client.post("/settings/pick-folder")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "D:/Papers"

    @patch("src.web.routes.settings.subprocess.run")
    def test_pick_folder_returns_empty_on_cancel(
        self, mock_run: MagicMock, client: TestClient
    ) -> None:
        """POST /settings/pick-folder returns empty path when user cancels."""
        mock_run.return_value = MagicMock(stdout="\n", returncode=0)
        response = client.post("/settings/pick-folder")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == ""

    @patch("src.web.routes.settings.subprocess.run")
    def test_pick_folder_handles_timeout(
        self, mock_run: MagicMock, client: TestClient
    ) -> None:
        """POST /settings/pick-folder returns 408 on subprocess timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="picker", timeout=120)
        response = client.post("/settings/pick-folder")
        assert response.status_code == 408
        data = response.json()
        assert data["path"] == ""
        assert "Timeout" in data["error"]

    @patch("src.web.routes.settings.subprocess.run")
    def test_pick_folder_handles_error(
        self, mock_run: MagicMock, client: TestClient
    ) -> None:
        """POST /settings/pick-folder returns 500 on unexpected error."""
        mock_run.side_effect = OSError("tkinter not available")
        response = client.post("/settings/pick-folder")
        assert response.status_code == 500
        data = response.json()
        assert data["path"] == ""
        assert "error" in data


# ============================================================
# Settings page browse buttons
# ============================================================


class TestSettingsPageBrowseButtons:
    """Tests that browse buttons appear on the settings page."""

    def test_settings_page_has_browse_buttons(self, client: TestClient) -> None:
        """GET /settings includes browse buttons for all 4 path fields."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert 'data-target="library_root"' in response.text
        assert 'data-target="vault_path"' in response.text
        assert 'data-target="style_folder"' in response.text
        assert 'data-target="watch_folder"' in response.text

    def test_settings_page_has_folder_picker_script(
        self, client: TestClient
    ) -> None:
        """GET /settings includes the folder picker JavaScript."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert "/settings/pick-folder" in response.text
