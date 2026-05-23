"""Tests for POST /import/pick-pdf endpoint (manual PDF import).

Covers:
- Modification C: UI manual import via file picker subprocess
- Successful PDF selection and import
- Cancelled dialog (empty path)
- Subprocess timeout
- Subprocess error
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.application.import_service import ImportResult

# ============================================================
# Pick PDF route tests
# ============================================================


class TestPickPdfRoute:
    """Tests for POST /import/pick-pdf endpoint."""

    @patch("src.web.routes.import_status.subprocess.run")
    def test_pick_pdf_success(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Successful PDF selection triggers handle_new_pdf and redirects."""
        mock_run.return_value = MagicMock(
            stdout="D:/papers/test.pdf\n",
            returncode=0,
        )
        mock_import_service.handle_new_pdf.return_value = ImportResult(
            pdf_path="D:/papers/test.pdf",
            status="success",
            message="",
        )

        resp = client.post("/import/pick-pdf", follow_redirects=False)
        # Should redirect to /import with result parameter
        assert resp.status_code == 303
        assert "/import" in resp.headers["location"]
        mock_import_service.handle_new_pdf.assert_called_once_with("D:/papers/test.pdf")

    @patch("src.web.routes.import_status.subprocess.run")
    def test_pick_pdf_cancelled(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Cancelled dialog (empty path) redirects without calling import."""
        mock_run.return_value = MagicMock(
            stdout="\n",
            returncode=0,
        )

        resp = client.post("/import/pick-pdf", follow_redirects=False)
        assert resp.status_code == 303
        assert "/import" in resp.headers["location"]
        assert "cancelled" in resp.headers["location"]
        mock_import_service.handle_new_pdf.assert_not_called()

    @patch("src.web.routes.import_status.subprocess.run")
    def test_pick_pdf_timeout(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Subprocess timeout returns JSON error."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=120)

        resp = client.post("/import/pick-pdf")
        assert resp.status_code == 408
        data = resp.json()
        assert "error" in data

    @patch("src.web.routes.import_status.subprocess.run")
    def test_pick_pdf_subprocess_error(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Subprocess error returns JSON error."""
        mock_run.side_effect = OSError("spawn failed")

        resp = client.post("/import/pick-pdf")
        assert resp.status_code == 500
        data = resp.json()
        assert "error" in data

    @patch("src.web.routes.import_status.subprocess.run")
    def test_pick_pdf_import_result_in_history(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """After successful import, result should be accessible in redirect."""
        mock_run.return_value = MagicMock(
            stdout="D:/papers/test.pdf\n",
            returncode=0,
        )
        mock_import_service.handle_new_pdf.return_value = ImportResult(
            pdf_path="D:/papers/test.pdf",
            status="success",
            message="",
        )

        resp = client.post("/import/pick-pdf", follow_redirects=False)
        assert resp.status_code == 303
        location = resp.headers["location"]
        assert "result=success" in location


class TestImportPageHasPickButton:
    """Verify the import page includes the manual import button."""

    def test_import_page_has_pick_pdf_button(self, client: TestClient) -> None:
        """GET /import should render a 'PDFを取り込む' button."""
        resp = client.get("/import")
        assert resp.status_code == 200
        assert "pick-pdf" in resp.text
        assert "PDFを取り込む" in resp.text

    def test_import_page_has_processing_indicator(self, client: TestClient) -> None:
        """The pick button area should include a processing indicator element."""
        resp = client.get("/import")
        assert resp.status_code == 200
        assert "pick-pdf-spinner" in resp.text
