"""Tests for lifespan watcher integration and extract_full_text config wiring.

Covers:
- Modification A: extract_full_text setting is passed to ImportAppService
- Modification B: FolderWatcher is started/stopped in lifespan
- Thread safety of the watcher callback
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from fastapi.testclient import TestClient

# ============================================================
# Helpers
# ============================================================


def _make_config(tmp_path: Path, **overrides: object) -> Path:
    """Create a temporary config.yaml with given overrides."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir(exist_ok=True)
    library_dir = tmp_path / "library"
    library_dir.mkdir(exist_ok=True)

    config = {
        "paths": {
            "library_root": str(library_dir),
            "vault_path": str(tmp_path / "vault"),
            "style_folder": "",
            "watch_folder": str(watch_dir),
        },
        "vault_name": "TestVault",
        "server": {"host": "127.0.0.1", "port": 12000},
        "import_settings": {
            "unsorted_folder_name": "未整理",
            "watch_interval_sec": 2,
            "contact_email": "test@example.com",
            "extract_full_text": overrides.get("extract_full_text", False),
        },
    }

    # Apply path overrides
    if "watch_folder" in overrides:
        config["paths"]["watch_folder"] = overrides["watch_folder"]

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    return config_file


# ============================================================
# Modification A: extract_full_text wiring
# ============================================================


class TestExtractFullTextWiring:
    """Verify that extract_full_text from config is passed to ImportAppService."""

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_extract_full_text_true_is_passed(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When extract_full_text=True in config, ImportAppService receives it."""
        config_path = _make_config(tmp_path, extract_full_text=True)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher") as mock_watcher_cls:
                mock_watcher_instance = MagicMock()
                mock_watcher_cls.return_value = mock_watcher_instance

                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        svc = app.state.import_service
                        assert svc._extract_full_text is True

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_extract_full_text_false_is_default(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When extract_full_text=False (default) in config, ImportAppService receives False."""
        config_path = _make_config(tmp_path, extract_full_text=False)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher") as mock_watcher_cls:
                mock_watcher_instance = MagicMock()
                mock_watcher_cls.return_value = mock_watcher_instance

                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        svc = app.state.import_service
                        assert svc._extract_full_text is False


# ============================================================
# Modification B: FolderWatcher integration
# ============================================================


class TestFolderWatcherIntegration:
    """Verify FolderWatcher lifecycle in app lifespan."""

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_watcher_starts_when_watch_folder_exists(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Watcher should start when watch_folder is configured and exists."""
        config_path = _make_config(tmp_path)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher") as mock_watcher_cls:
                mock_watcher_instance = MagicMock()
                mock_watcher_cls.return_value = mock_watcher_instance

                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        mock_watcher_instance.start.assert_called_once()

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_watcher_stops_on_shutdown(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Watcher should stop when the app shuts down (after yield)."""
        config_path = _make_config(tmp_path)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher") as mock_watcher_cls:
                mock_watcher_instance = MagicMock()
                mock_watcher_cls.return_value = mock_watcher_instance

                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        pass  # App starts and stops within this block
                    # After exiting the TestClient context, shutdown runs
                    mock_watcher_instance.stop.assert_called_once()

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_watcher_skipped_when_watch_folder_empty(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Watcher should not start when watch_folder is empty string."""
        config_path = _make_config(tmp_path, watch_folder="")

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher") as mock_watcher_cls:
                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        mock_watcher_cls.assert_not_called()

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_watcher_skipped_when_folder_does_not_exist(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Watcher should not start when watch_folder path does not exist."""
        nonexistent = str(tmp_path / "nonexistent_dir")
        config_path = _make_config(tmp_path, watch_folder=nonexistent)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher") as mock_watcher_cls:
                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        mock_watcher_cls.assert_not_called()

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_watcher_callback_calls_handle_new_pdf(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The watcher callback should invoke import_service.handle_new_pdf."""
        config_path = _make_config(tmp_path)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        captured_callback = None

        def capture_watcher_init(**kwargs: object) -> MagicMock:
            nonlocal captured_callback
            captured_callback = kwargs.get("on_new_pdf")
            watcher = MagicMock()
            return watcher

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch("src.web.app.FolderWatcher", side_effect=capture_watcher_init):
                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    with TestClient(app):
                        # Simulate the callback being called by the watcher
                        assert captured_callback is not None
                        # Mock handle_new_pdf to avoid actual processing
                        app.state.import_service.handle_new_pdf = MagicMock()
                        captured_callback("D:/test/paper.pdf")
                        app.state.import_service.handle_new_pdf.assert_called_once_with(
                            "D:/test/paper.pdf"
                        )

    @patch("src.adapters.crossref_client.CrossRefMetadataResolver")
    @patch("src.web.app.FilesystemPaperRepository")
    def test_app_starts_even_when_watcher_fails(
        self,
        mock_paper_repo_cls: MagicMock,
        mock_crossref_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """App should start even if FolderWatcher raises an exception."""
        config_path = _make_config(tmp_path)

        mock_repo_instance = MagicMock()
        mock_repo_instance.find_all.return_value = []
        mock_paper_repo_cls.return_value = mock_repo_instance

        with patch("src.web.app.load_settings") as mock_load:
            with open(config_path, encoding="utf-8") as f:
                mock_load.return_value = yaml.safe_load(f)

            with patch(
                "src.web.app.FolderWatcher",
                side_effect=Exception("Watcher init failed"),
            ):
                with patch("src.web.app.get_vault_name", return_value="TestVault"):
                    from src.web.app import create_app

                    app = create_app()
                    # App should still start without errors
                    with TestClient(app) as client:
                        response = client.get("/import")
                        assert response.status_code == 200


# ============================================================
# Thread safety
# ============================================================


class TestWatcherThreadSafety:
    """Verify thread-safe access from watcher callback."""

    def test_handle_new_pdf_with_lock(self) -> None:
        """handle_new_pdf calls through the lock wrapper are serialized."""
        from src.web.app import _make_threadsafe_callback

        mock_service = MagicMock()
        lock = threading.Lock()
        callback = _make_threadsafe_callback(mock_service, lock)

        # Simulate concurrent calls
        results = []

        def call_callback(path: str) -> None:
            callback(path)
            results.append(path)

        threads = [
            threading.Thread(target=call_callback, args=(f"paper_{i}.pdf",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert mock_service.handle_new_pdf.call_count == 5
        assert len(results) == 5
