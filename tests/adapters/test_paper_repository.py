"""Tests for FilesystemPaperRepository.

Uses pytest tmp_path fixture for isolated filesystem operations.
Covers happy path, boundary values, and error cases.
"""

from __future__ import annotations

from datetime import datetime
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
# Fixtures
# ============================================================


def _make_metadata(
    title: str = "Test Paper Title",
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    doi_str: str | None = "10.1234/test.5678",
    abstract: str = "",
    memo: str = "",
    journal: str = "",
    journal_abbrev: str = "",
    volume: str = "",
    issue: str = "",
    pages: str = "",
) -> Metadata:
    """Helper to build Metadata."""
    authors = (Author(family_name=family, given_name=given),)
    doi = DOI(doi_str) if doi_str else None
    return Metadata(
        title=title,
        authors=authors,
        year=PublicationYear(year),
        doi=doi,
        abstract=abstract,
        memo=memo,
        journal=journal,
        journal_abbrev=journal_abbrev,
        volume=volume,
        issue=issue,
        pages=pages,
    )


def _make_paper(
    metadata: Metadata | None = None,
    pdf_content: bytes = b"%PDF-1.4 test content",
) -> Paper:
    """Helper to build a Paper with associated metadata."""
    if metadata is None:
        metadata = _make_metadata()
    return Paper.create(
        metadata=metadata,
        pdf_path="placeholder.pdf",
        pdf_head_bytes=pdf_content if metadata.doi is None else None,
    )


def _setup_library(tmp_path: Path) -> Path:
    """Create a library root directory."""
    library_root = tmp_path / "library"
    library_root.mkdir()
    return library_root


def _create_paper_files(
    library_root: Path,
    paper: Paper,
) -> tuple[Path, Path]:
    """Create PDF and MD files for a paper in the correct folder."""
    folder = library_root / paper.initial_letter.letter
    folder.mkdir(exist_ok=True)

    file_name = paper.build_file_name()
    pdf_path = folder / f"{file_name.value}.pdf"
    md_path = folder / f"{file_name.value}.md"

    pdf_path.write_bytes(b"%PDF-1.4 test content")
    md_path.write_text(paper.to_markdown_note(), encoding="utf-8")

    return pdf_path, md_path


# ============================================================
# Construction / Initialization
# ============================================================


class TestFilesystemPaperRepositoryInit:
    """Tests for repository initialization and folder scanning."""

    def test_init_creates_instance(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        assert repo is not None

    def test_init_with_nonexistent_root_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            FilesystemPaperRepository(nonexistent)

    def test_scan_empty_library(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()
        assert repo.find_all() == []

    def test_scan_creates_initial_letter_folders(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()
        # Should create A-Z and # folders
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert (library_root / letter).is_dir()
        assert (library_root / "#").is_dir()

    def test_scan_loads_existing_papers(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _create_paper_files(library_root, paper)

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        result = repo.find_all()
        assert len(result) == 1
        assert result[0].id == paper.id

    def test_scan_loads_multiple_papers(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)

        meta1 = _make_metadata(
            title="Paper One", family="Alpha", doi_str="10.1234/alpha.001"
        )
        meta2 = _make_metadata(
            title="Paper Two", family="Beta", doi_str="10.1234/beta.002"
        )
        paper1 = _make_paper(metadata=meta1)
        paper2 = _make_paper(metadata=meta2)

        _create_paper_files(library_root, paper1)
        _create_paper_files(library_root, paper2)

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        result = repo.find_all()
        assert len(result) == 2

    def test_scan_ignores_pdf_without_md(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        folder = library_root / "S"
        folder.mkdir()
        (folder / "Some Paper.pdf").write_bytes(b"%PDF-1.4")
        # No .md companion

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        assert repo.find_all() == []

    def test_scan_ignores_md_without_pdf(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        folder = library_root / "S"
        folder.mkdir()
        (folder / "Some Paper.md").write_text(
            "---\npaper_id: \"test\"\n---\n", encoding="utf-8"
        )
        # No .pdf companion

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        assert repo.find_all() == []

    def test_scan_loads_md_only_paper_with_doi(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        metadata = _make_metadata(doi_str="10.1234/mdonly.001")
        paper = Paper.create(metadata=metadata)
        folder = library_root / paper.initial_letter.letter
        folder.mkdir(exist_ok=True)
        md_path = folder / f"{paper.build_file_name().value}.md"
        md_path.write_text(paper.to_markdown_note(), encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.note_path == str(md_path)
        assert found.pdf_path is None
        assert not found.has_pdf


# ============================================================
# find_by_id
# ============================================================


class TestFindById:
    """Tests for find_by_id method."""

    def test_find_existing_paper(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _create_paper_files(library_root, paper)

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        result = repo.find_by_id(paper.id)
        assert result is not None
        assert result.id == paper.id
        assert result.metadata.title == paper.metadata.title

    def test_find_nonexistent_paper_returns_none(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        result = repo.find_by_id(PaperId("10.9999/nonexistent"))
        assert result is None


# ============================================================
# save
# ============================================================


class TestSave:
    """Tests for save method."""

    def test_save_new_paper_creates_files(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        paper = _make_paper()
        # Set the pdf_path to a source file
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 source content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        # Paper should be findable
        found = repo.find_by_id(paper.id)
        assert found is not None

        # Files should exist in the correct folder
        folder = library_root / paper.initial_letter.letter
        file_name = paper.build_file_name()
        assert (folder / f"{file_name.value}.pdf").exists()
        assert (folder / f"{file_name.value}.md").exists()

    def test_save_updates_existing_paper(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _create_paper_files(library_root, paper)

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        # Update metadata
        new_meta = _make_metadata(
            title="Updated Title",
            family="Smith",
            given="John",
            doi_str="10.1234/test.5678",
        )
        paper.update_metadata(new_meta)
        repo.save(paper)

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.title == "Updated Title"

    def test_save_adds_to_cache(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        assert len(repo.find_all()) == 0

        paper = _make_paper()
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)
        assert len(repo.find_all()) == 1

    def test_save_paper_without_doi_uses_sha(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        meta = _make_metadata(doi_str=None)
        paper = _make_paper(metadata=meta, pdf_content=b"%PDF-1.4 unique bytes")
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 unique bytes")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.id.value.startswith("sha256:")

    def test_save_md_only_paper_creates_note_without_pdf(
        self,
        tmp_path: Path,
    ) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()
        metadata = _make_metadata(doi_str="10.1234/mdonly.002")
        paper = Paper.create(metadata=metadata)

        repo.save(paper)

        found = repo.find_by_id(paper.id)
        assert found is not None
        folder = library_root / paper.initial_letter.letter
        file_name = paper.build_file_name()
        assert (folder / f"{file_name.value}.md").exists()
        assert not (folder / f"{file_name.value}.pdf").exists()
        assert found.pdf_path is None

    def test_attach_pdf_to_md_only_paper_updates_note_and_cache(
        self,
        tmp_path: Path,
    ) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()
        metadata = _make_metadata(doi_str="10.1234/mdonly.003")
        paper = Paper.create(metadata=metadata)
        repo.save(paper)
        source_pdf = tmp_path / "selected.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 attached content")

        updated = repo.attach_pdf(paper.id, str(source_pdf))

        assert updated.has_pdf
        assert updated.pdf_path is not None
        target_pdf = Path(updated.pdf_path)
        assert target_pdf.exists()
        assert target_pdf.name == f"{updated.build_file_name().value}.pdf"
        assert Path(updated.note_path or "").read_text(encoding="utf-8").count(
            target_pdf.name
        ) >= 1


# ============================================================
# delete
# ============================================================


class TestDelete:
    """Tests for delete method."""

    def test_delete_existing_paper(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        pdf_path, md_path = _create_paper_files(library_root, paper)

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        repo.delete(paper.id)

        assert repo.find_by_id(paper.id) is None
        assert not pdf_path.exists()
        assert not md_path.exists()

    def test_delete_nonexistent_paper_raises(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        with pytest.raises(KeyError):
            repo.delete(PaperId("10.9999/nonexistent"))


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    """Tests for edge cases and special characters."""

    def test_paper_with_hash_initial(self, tmp_path: Path) -> None:
        """Papers with non-ASCII author names go to # folder."""
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        meta = _make_metadata(
            title="Non-ASCII Author",
            family="田中",
            given="太郎",
            doi_str="10.1234/tanaka.001",
        )
        paper = _make_paper(metadata=meta)
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.initial_letter.letter == "#"

    def test_md_frontmatter_roundtrip(self, tmp_path: Path) -> None:
        """Saving and loading preserves all metadata fields."""
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        meta = _make_metadata(
            title="Roundtrip Test",
            family="Jones",
            given="Alice",
            doi_str="10.5678/roundtrip.001",
        )
        paper = _make_paper(metadata=meta)
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        # Create a new repo instance to force reload from disk
        repo2 = FilesystemPaperRepository(library_root)
        repo2.scan()

        found = repo2.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.title == "Roundtrip Test"
        assert found.metadata.first_author.family_name == "Jones"
        assert found.metadata.first_author.given_name == "Alice"
        assert found.metadata.year.value == 2024
        assert found.metadata.doi is not None
        assert found.metadata.doi.value == "10.5678/roundtrip.001"

    def test_md_frontmatter_roundtrip_preserves_abstract(
        self, tmp_path: Path
    ) -> None:
        """Saving and loading preserves abstract text."""
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        meta = _make_metadata(
            title="Abstract Roundtrip",
            family="Jones",
            doi_str="10.5678/abstract.001",
            abstract="This study evaluates regeneration outcomes.",
        )
        paper = _make_paper(metadata=meta)
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        repo2 = FilesystemPaperRepository(library_root)
        repo2.scan()

        found = repo2.find_by_id(paper.id)
        assert found is not None
        assert (
            found.metadata.abstract
            == "This study evaluates regeneration outcomes."
        )

    def test_md_frontmatter_roundtrip_preserves_memo(
        self, tmp_path: Path
    ) -> None:
        """Saving and loading preserves memo text."""
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        meta = _make_metadata(
            title="Memo Roundtrip",
            family="Jones",
            doi_str="10.5678/memo.001",
            memo="Discuss in journal club.",
        )
        paper = _make_paper(metadata=meta)
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        repo2 = FilesystemPaperRepository(library_root)
        repo2.scan()

        found = repo2.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.memo == "Discuss in journal club."

    def test_md_frontmatter_roundtrip_preserves_bibliographic_fields(
        self, tmp_path: Path
    ) -> None:
        """Saving and loading preserves bibliographic frontmatter fields."""
        library_root = _setup_library(tmp_path)
        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        meta = _make_metadata(
            title="Bibliographic Roundtrip",
            family="Okita",
            doi_str="10.5678/biblio.001",
            journal="Stem Cell Reports",
            journal_abbrev="Stem Cell Rep",
            volume="12",
            issue="3",
            pages="2364-2370",
        )
        paper = _make_paper(metadata=meta)
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_bytes(b"%PDF-1.4 content")
        paper.pdf_path = str(source_pdf)

        repo.save(paper)

        repo2 = FilesystemPaperRepository(library_root)
        repo2.scan()

        found = repo2.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.journal == "Stem Cell Reports"
        assert found.metadata.journal_abbrev == "Stem Cell Rep"
        assert found.metadata.volume == "12"
        assert found.metadata.issue == "3"
        assert found.metadata.pages == "2364-2370"

    def test_scan_reads_bibliographic_fields_as_safe_strings(
        self, tmp_path: Path
    ) -> None:
        """Numeric frontmatter values for bibliographic fields stay loadable."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        edited_note = paper.to_markdown_note().replace(
            f'doi: "{paper.metadata.doi.value if paper.metadata.doi else ""}"\n',
            f'doi: "{paper.metadata.doi.value if paper.metadata.doi else ""}"\n'
            'journal: "Journal of Testing"\n'
            'journal_abbrev: "J Test"\n'
            "volume: 12\n"
            "issue: 3\n"
            "pages: 45\n",
        )
        md_path.write_text(edited_note, encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.journal == "Journal of Testing"
        assert found.metadata.journal_abbrev == "J Test"
        assert found.metadata.volume == "12"
        assert found.metadata.issue == "3"
        assert found.metadata.pages == "45"

    def test_scan_preserves_paper_when_authors_are_json_string(
        self, tmp_path: Path
    ) -> None:
        """Obsidian property edits may serialize authors as a JSON string."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        pdf_path, md_path = _create_paper_files(library_root, paper)
        edited_note = paper.to_markdown_note().replace(
            "authors:\n"
            '  - family: "Smith"\n'
            '    given: "John"\n',
            'authors: \'[{"family":"Okita","given":"K"}]\'\n',
        )
        edited_note = edited_note.replace(
            'abstract: ""',
            'abstract: "Manually entered abstract."',
        )
        md_path.write_text(edited_note, encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.first_author.family_name == "Okita"
        assert found.metadata.first_author.given_name == "K"
        assert found.metadata.abstract == "Manually entered abstract."
        assert Path(found.pdf_path) == pdf_path

    def test_scan_preserves_multiline_abstract_property(
        self, tmp_path: Path
    ) -> None:
        """Multiline abstract values edited in Obsidian stay loadable."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        edited_note = paper.to_markdown_note().replace(
            'abstract: ""',
            "abstract: |-\n"
            "  ## Abstract\n"
            "  ## Purpose of review\n"
            "  Manually entered abstract.\n",
        )
        md_path.write_text(edited_note, encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert "## Abstract" in found.metadata.abstract
        assert "Manually entered abstract." in found.metadata.abstract

    def test_scan_preserves_multiline_memo_property(
        self, tmp_path: Path
    ) -> None:
        """Multiline memo values edited in Obsidian stay loadable."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        edited_note = paper.to_markdown_note().replace(
            'memo: ""',
            "memo: |-\n"
            "  - Important for iPS transplantation review\n"
            "  - Check safety concerns\n",
        )
        md_path.write_text(edited_note, encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert "Important for iPS transplantation review" in found.metadata.memo
        assert "Check safety concerns" in found.metadata.memo

    def test_scan_preserves_paper_when_frontmatter_yaml_is_damaged(
        self, tmp_path: Path
    ) -> None:
        """Damaged Obsidian properties should not remove the paper from lists."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        md_path.write_text(
            "---\n"
            f'paper_id: "{paper.id.value}"\n'
            'title: "Test Paper Title"\n'
            'authors: [{"family":"Okita","given":"K"}\n'
            "year: 2011\n"
            f'doi: "{paper.metadata.doi.value if paper.metadata.doi else ""}"\n'
            "abstract: |-\n"
            "  ## Abstract\n"
            "  Manually entered abstract.\n"
            'initial_letter: "O"\n'
            "---\n",
            encoding="utf-8",
        )

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.title == "Test Paper Title"
        assert found.metadata.year.value == 2011
        assert "Manually entered abstract." in found.metadata.abstract

    def test_scan_preserves_paper_when_imported_at_is_datetime(
        self, tmp_path: Path
    ) -> None:
        """python-frontmatter may parse imported_at into datetime."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        edited_note = paper.to_markdown_note().replace(
            'imported_at: "',
            "imported_at: ",
        )
        edited_note = edited_note.replace('"\nsource: "crossref"', '\nsource: "crossref"')
        md_path.write_text(edited_note, encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert isinstance(found.imported_at, datetime)

    def test_scan_preserves_paper_when_year_is_string(
        self, tmp_path: Path
    ) -> None:
        """Obsidian may serialize numeric properties as strings."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        edited_note = paper.to_markdown_note().replace("year: 2024", 'year: "2024"')
        md_path.write_text(edited_note, encoding="utf-8")

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.year.value == 2024

    def test_scan_does_not_extract_abstract_from_markdown_body(
        self, tmp_path: Path
    ) -> None:
        """Only frontmatter abstract is displayed; body extraction is disabled."""
        library_root = _setup_library(tmp_path)
        paper = _make_paper()
        _pdf_path, md_path = _create_paper_files(library_root, paper)
        md_path.write_text(
            paper.to_markdown_note()
            + "\n---\n\n## Abstract\nBody abstract should be ignored.\n",
            encoding="utf-8",
        )

        repo = FilesystemPaperRepository(library_root)
        repo.scan()

        found = repo.find_by_id(paper.id)
        assert found is not None
        assert found.metadata.abstract == ""
