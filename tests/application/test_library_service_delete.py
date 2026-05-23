"""Tests for LibraryAppService.delete_paper and rescan methods.

Uses mocked PaperRepository to isolate from filesystem.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.application.library_service import LibraryAppService
from src.domain.paper import (
    DOI,
    Author,
    Metadata,
    Paper,
    PaperId,
    PublicationYear,
)
from src.domain.ports import PaperRepository

# ============================================================
# Helpers
# ============================================================


def _make_paper(paper_id: str = "10.1234/test.001") -> Paper:
    """Create a sample Paper for testing."""
    metadata = Metadata(
        title="Test Paper",
        authors=(Author(family_name="Smith", given_name="John"),),
        year=PublicationYear(2024),
        doi=DOI(paper_id),
    )
    return Paper.create(metadata=metadata, pdf_path="test.pdf")


def _make_mock_repo(papers: list[Paper] | None = None) -> MagicMock:
    """Create a mock PaperRepository.

    Note: scan() is not in the PaperRepository ABC but is called by
    LibraryAppService.rescan(). We add it explicitly to the mock.
    """
    repo = MagicMock(spec=PaperRepository)
    paper_list = papers or []
    repo.find_all.return_value = paper_list
    repo.find_by_id.side_effect = lambda pid: next(
        (p for p in paper_list if p.id == pid), None
    )
    # scan() is defined on FilesystemPaperRepository, not on the ABC
    repo.scan = MagicMock()
    return repo


# ============================================================
# Tests: delete_paper
# ============================================================


class TestDeletePaper:
    """Tests for LibraryAppService.delete_paper."""

    def test_delete_existing_paper_returns_true(self) -> None:
        """delete_paper returns True and calls repo.delete for existing paper."""
        paper = _make_paper()
        repo = _make_mock_repo([paper])
        service = LibraryAppService(repo)

        result = service.delete_paper(paper.id)

        assert result is True
        repo.delete.assert_called_once_with(paper.id)

    def test_delete_nonexistent_paper_returns_false(self) -> None:
        """delete_paper returns False for unknown paper_id."""
        repo = _make_mock_repo([])
        service = LibraryAppService(repo)

        result = service.delete_paper(PaperId("10.9999/nonexistent"))

        assert result is False
        repo.delete.assert_not_called()

    def test_delete_does_not_affect_other_papers(self) -> None:
        """delete_paper only removes the specified paper."""
        paper1 = _make_paper("10.1234/test.001")
        paper2 = _make_paper("10.5678/test.002")
        repo = _make_mock_repo([paper1, paper2])
        service = LibraryAppService(repo)

        service.delete_paper(paper1.id)

        repo.delete.assert_called_once_with(paper1.id)


# ============================================================
# Tests: rescan
# ============================================================


class TestRescan:
    """Tests for LibraryAppService.rescan."""

    def test_rescan_calls_scan_and_returns_count(self) -> None:
        """rescan calls repo.scan() and returns paper count."""
        paper = _make_paper()
        repo = _make_mock_repo([paper])
        service = LibraryAppService(repo)

        count = service.rescan()

        repo.scan.assert_called_once()
        assert count == 1

    def test_rescan_with_empty_library(self) -> None:
        """rescan returns 0 for an empty library."""
        repo = _make_mock_repo([])
        service = LibraryAppService(repo)

        count = service.rescan()

        repo.scan.assert_called_once()
        assert count == 0
