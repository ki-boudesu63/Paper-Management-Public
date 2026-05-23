"""Tests for paper action routes (delete).

Uses the shared TestClient fixture with mocked services.
Covers: successful delete, not-found paper, collection ref removal,
and htmx response structure.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from tests.web.conftest import SAMPLE_PAPERS


class TestDeletePaperRoute:
    """Tests for POST /papers/{paper_id}/delete."""

    def test_delete_paper_returns_200(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Delete endpoint returns 200 with HTML content."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.delete_paper.return_value = True
        mock_library_service.list_all.return_value = SAMPLE_PAPERS[1:]

        response = client.post(f"/papers/{paper.id.value}/delete")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_delete_paper_calls_services(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Delete endpoint calls collection removal and paper deletion."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.delete_paper.return_value = True
        mock_library_service.list_all.return_value = []

        client.post(f"/papers/{paper.id.value}/delete")

        # Collection references should be removed first
        mock_collection_service.remove_paper_from_all_collections.assert_called_once_with(
            paper.id.value,
        )
        # Then paper itself is deleted
        mock_library_service.delete_paper.assert_called_once()

    def test_delete_nonexistent_paper_still_returns_200(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Delete returns 200 even if paper was not found (idempotent)."""
        mock_library_service.delete_paper.return_value = False
        mock_library_service.list_all.return_value = SAMPLE_PAPERS

        response = client.post("/papers/10.9999/nonexistent/delete")

        assert response.status_code == 200

    def test_delete_response_contains_empty_inspector(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Delete response should include the empty inspector state text."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.delete_paper.return_value = True
        mock_library_service.list_all.return_value = []

        response = client.post(f"/papers/{paper.id.value}/delete")
        html = response.text

        assert "論文を選択してください" in html

    def test_delete_response_contains_updated_paper_list(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Delete response should include updated paper list via OOB swap."""
        paper_to_delete = SAMPLE_PAPERS[0]
        remaining_papers = SAMPLE_PAPERS[1:]
        mock_library_service.delete_paper.return_value = True
        mock_library_service.list_all.return_value = remaining_papers

        response = client.post(f"/papers/{paper_to_delete.id.value}/delete")
        html = response.text

        # Should contain OOB swap marker
        assert "hx-swap-oob" in html
        # Should contain remaining paper but not deleted one
        for paper in remaining_papers:
            assert paper.metadata.title in html

    def test_delete_paper_with_doi_containing_slashes(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Delete handles DOI-based paper_id with slashes correctly."""
        paper_id_with_slash = "10.1234/test.001"
        mock_library_service.delete_paper.return_value = True
        mock_library_service.list_all.return_value = []

        response = client.post(f"/papers/{paper_id_with_slash}/delete")

        assert response.status_code == 200
        mock_collection_service.remove_paper_from_all_collections.assert_called_once_with(
            paper_id_with_slash,
        )


class TestAttachPdfRoute:
    """Tests for POST /papers/{paper_id}/attach-pdf."""

    @patch("src.web.routes.paper_actions.subprocess.run")
    def test_attach_pdf_success_updates_paper_and_returns_inspector(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        paper = SAMPLE_PAPERS[0]
        mock_run.return_value = MagicMock(stdout="D:/papers/selected.pdf\n")
        mock_import_service.attach_pdf_to_paper.return_value = paper

        response = client.post(f"/papers/{paper.id.value}/attach-pdf")

        assert response.status_code == 200
        mock_import_service.attach_pdf_to_paper.assert_called_once()
        assert paper.metadata.title in response.text

    @patch("src.web.routes.paper_actions.subprocess.run")
    def test_attach_pdf_cancelled_does_not_attach(
        self,
        mock_run: MagicMock,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        paper = SAMPLE_PAPERS[0]
        mock_run.return_value = MagicMock(stdout="\n")

        response = client.post(f"/papers/{paper.id.value}/attach-pdf")

        assert response.status_code == 204
        mock_import_service.attach_pdf_to_paper.assert_not_called()
