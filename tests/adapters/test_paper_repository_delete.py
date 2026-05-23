"""Tests for FilesystemPaperRepository.delete with assets folder handling.

Covers: normal delete, assets folder removal, missing files (idempotent),
missing assets folder, and KeyError on unknown paper_id.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.filesystem.paper_repository import FilesystemPaperRepository
from src.domain.paper import (
    DOI,
    Author,
    Metadata,
    Paper,
    PaperId,
    PublicationYear,
)

# ============================================================
# Helpers
# ============================================================


def _make_paper(
    paper_id: str = "10.1234/test.001",
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    title: str = "Test Paper",
) -> Paper:
    """Build a Paper via create() for testing."""
    metadata = Metadata(
        title=title,
        authors=(Author(family_name=family, given_name=given),),
        year=PublicationYear(year),
        doi=DOI(paper_id),
    )
    return Paper.create(
        metadata=metadata,
        pdf_path="placeholder.pdf",
    )


def _setup_repo_with_paper(
    tmp_path: Path,
) -> tuple[FilesystemPaperRepository, Paper, Path, Path]:
    """Set up a repository with one saved paper. Returns (repo, paper, pdf_path, md_path)."""
    library_root = tmp_path / "library"
    library_root.mkdir()

    repo = FilesystemPaperRepository(library_root)
    repo.scan()

    paper = _make_paper()
    # Create a source PDF so save() can copy it
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 test content")
    paper.pdf_path = str(source_pdf)

    repo.save(paper)

    pdf_path = Path(paper.pdf_path)
    md_path = Path(paper.note_path)
    return repo, paper, pdf_path, md_path


# ============================================================
# Tests
# ============================================================


class TestDeletePaper:
    """Tests for FilesystemPaperRepository.delete."""

    def test_delete_removes_pdf_and_md(self, tmp_path: Path) -> None:
        """Delete should remove both PDF and MD files."""
        repo, paper, pdf_path, md_path = _setup_repo_with_paper(tmp_path)

        assert pdf_path.exists()
        assert md_path.exists()

        repo.delete(paper.id)

        assert not pdf_path.exists()
        assert not md_path.exists()

    def test_delete_removes_from_cache(self, tmp_path: Path) -> None:
        """Delete should remove the paper from the in-memory cache."""
        repo, paper, _, _ = _setup_repo_with_paper(tmp_path)

        assert repo.find_by_id(paper.id) is not None

        repo.delete(paper.id)

        assert repo.find_by_id(paper.id) is None
        assert paper.id not in [p.id for p in repo.find_all()]

    def test_delete_removes_assets_folder(self, tmp_path: Path) -> None:
        """Delete should also remove the <stem>.assets/ directory."""
        repo, paper, pdf_path, _ = _setup_repo_with_paper(tmp_path)

        # Create an assets folder with a figure file
        assets_dir = pdf_path.parent / f"{pdf_path.stem}.assets"
        assets_dir.mkdir()
        (assets_dir / "figure-1.png").write_bytes(b"fake png data")

        assert assets_dir.exists()

        repo.delete(paper.id)

        assert not assets_dir.exists()

    def test_delete_without_assets_folder_succeeds(self, tmp_path: Path) -> None:
        """Delete should succeed even when no assets folder exists."""
        repo, paper, pdf_path, _ = _setup_repo_with_paper(tmp_path)

        assets_dir = pdf_path.parent / f"{pdf_path.stem}.assets"
        assert not assets_dir.exists()

        # Should not raise
        repo.delete(paper.id)
        assert repo.find_by_id(paper.id) is None

    def test_delete_with_files_already_removed(self, tmp_path: Path) -> None:
        """Delete should succeed when PDF/MD have been manually deleted."""
        repo, paper, pdf_path, md_path = _setup_repo_with_paper(tmp_path)

        # Simulate manual deletion of files
        pdf_path.unlink()
        md_path.unlink()

        assert not pdf_path.exists()
        assert not md_path.exists()

        # Should not raise — cache removal still happens
        repo.delete(paper.id)
        assert repo.find_by_id(paper.id) is None

    def test_delete_unknown_paper_raises_key_error(self, tmp_path: Path) -> None:
        """Delete should raise KeyError for an unknown paper_id."""
        library_root = tmp_path / "library"
        library_root.mkdir()

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        with pytest.raises(KeyError, match="Paper not found"):
            repo.delete(PaperId("10.9999/nonexistent"))

    def test_delete_with_assets_containing_multiple_files(self, tmp_path: Path) -> None:
        """Delete should remove assets folder even with multiple files inside."""
        repo, paper, pdf_path, _ = _setup_repo_with_paper(tmp_path)

        # Create an assets folder with multiple figure files
        assets_dir = pdf_path.parent / f"{pdf_path.stem}.assets"
        assets_dir.mkdir()
        (assets_dir / "figure-1.png").write_bytes(b"fake png 1")
        (assets_dir / "figure-2.png").write_bytes(b"fake png 2")
        (assets_dir / "figure-3.png").write_bytes(b"fake png 3")

        repo.delete(paper.id)

        assert not assets_dir.exists()
