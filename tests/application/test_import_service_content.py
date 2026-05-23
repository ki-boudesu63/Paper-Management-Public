"""Tests for ImportAppService content extraction integration.

Tests the full-text + figure extraction pipeline step that runs
after a paper has been saved. All Docling interactions are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.application.import_service import ImportAppService
from src.application.metadata_buffer import MetadataBuffer
from src.application.pdf_content_extractor import ExtractedFigure, ExtractionResult
from src.domain.paper import DOI, Author, Metadata, Paper, PaperId, PublicationYear
from src.domain.ports import MetadataResolver, PaperRepository

# ============================================================
# Fixtures and helpers
# ============================================================


def _make_metadata(
    title: str = "Test Paper Title",
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    doi_value: str | None = "10.1234/test.001",
) -> Metadata:
    """Create a Metadata instance for testing."""
    doi = DOI(doi_value) if doi_value else None
    return Metadata(
        title=title,
        authors=(Author(family_name=family, given_name=given),),
        year=PublicationYear(year),
        doi=doi,
    )


def _create_test_pdf(
    path: Path, content: bytes = b"%PDF-1.4 test content" * 100
) -> Path:
    """Create a minimal test PDF file."""
    path.write_bytes(content)
    return path


class MockPaperRepository(PaperRepository):
    """In-memory mock of PaperRepository for testing."""

    def __init__(self, library_root: Path) -> None:
        self._papers: dict[PaperId, Paper] = {}
        self._library_root = library_root
        self._scan_called = False

    def find_by_id(self, paper_id: PaperId) -> Paper | None:
        return self._papers.get(paper_id)

    def find_all(self) -> list[Paper]:
        return list(self._papers.values())

    def save(self, paper: Paper) -> None:
        """Simulate filesystem save: set paths and write MD file."""
        folder = self._library_root / paper.initial_letter.letter
        folder.mkdir(exist_ok=True)

        file_name = paper.build_file_name()
        pdf_target = folder / f"{file_name.value}.pdf"
        md_target = folder / f"{file_name.value}.md"

        # Copy PDF if source exists
        source_pdf = Path(paper.pdf_path)
        if source_pdf.exists():
            import shutil

            shutil.copy2(str(source_pdf), str(pdf_target))

        # Write the MD note
        md_content = paper.to_markdown_note()
        md_target.write_text(md_content, encoding="utf-8")

        paper.pdf_path = str(pdf_target)
        paper.note_path = str(md_target)

        self._papers[paper.id] = paper

    def attach_pdf(self, paper_id: PaperId, pdf_path: str) -> Paper:
        """Attach a PDF to an existing paper."""
        paper = self._papers[paper_id]
        paper.pdf_path = pdf_path
        self._papers[paper_id] = paper
        return paper

    def delete(self, paper_id: PaperId) -> None:
        if paper_id not in self._papers:
            raise KeyError(f"Paper not found: {paper_id.value}")
        del self._papers[paper_id]

    def scan(self) -> None:
        self._scan_called = True


class MockMetadataResolver(MetadataResolver):
    """Mock MetadataResolver for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, Metadata | None] = {}

    def set_response(self, doi_value: str, metadata: Metadata | None) -> None:
        self._responses[doi_value] = metadata

    def resolve(self, doi: DOI) -> Metadata | None:
        return self._responses.get(doi.value)


@pytest.fixture()
def setup_with_extraction(
    tmp_path: Path,
) -> tuple[
    ImportAppService,
    MockPaperRepository,
    MockMetadataResolver,
    MetadataBuffer,
    Path,
]:
    """Create ImportAppService with extract_full_text=True."""
    library_root = tmp_path / "library"
    library_root.mkdir()

    repo = MockPaperRepository(library_root)
    resolver = MockMetadataResolver()
    buffer = MetadataBuffer()

    service = ImportAppService(
        paper_repo=repo,
        metadata_resolver=resolver,
        metadata_buffer=buffer,
        library_root=library_root,
        unsorted_folder_name="unsorted",
        extract_full_text=True,
    )

    return service, repo, resolver, buffer, library_root


@pytest.fixture()
def setup_without_extraction(
    tmp_path: Path,
) -> tuple[
    ImportAppService,
    MockPaperRepository,
    MockMetadataResolver,
    MetadataBuffer,
    Path,
]:
    """Create ImportAppService with extract_full_text=False."""
    library_root = tmp_path / "library"
    library_root.mkdir()

    repo = MockPaperRepository(library_root)
    resolver = MockMetadataResolver()
    buffer = MetadataBuffer()

    service = ImportAppService(
        paper_repo=repo,
        metadata_resolver=resolver,
        metadata_buffer=buffer,
        library_root=library_root,
        unsorted_folder_name="unsorted",
        extract_full_text=False,
    )

    return service, repo, resolver, buffer, library_root


# ============================================================
# Tests: Full text extraction enabled
# ============================================================


class TestImportWithContentExtraction:
    """Tests for import pipeline with full text extraction enabled."""

    def test_attach_pdf_to_paper_extracts_content_when_enabled(
        self,
        setup_with_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """Manual PDF attach runs content extraction when enabled."""
        service, repo, _, _, library_root = setup_with_extraction
        meta = _make_metadata(doi_value="10.1234/mdonly")
        note_path = library_root / "S" / "Smith 2024 - Test Paper Title.md"
        note_path.parent.mkdir()
        note_path.write_text("metadata note", encoding="utf-8")
        paper = Paper.create(metadata=meta, note_path=str(note_path))
        repo._papers[paper.id] = paper
        pdf_path = _create_test_pdf(library_root.parent / "selected.pdf")

        with patch.object(service, "_extract_and_append_content") as mock_extract:
            attached = service.attach_pdf_to_paper(paper.id, str(pdf_path))

        assert attached.pdf_path == str(pdf_path)
        mock_extract.assert_called_once_with(str(pdf_path), attached)

    def test_duplicate_md_only_attach_extracts_content_when_enabled(
        self,
        setup_with_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """Watcher duplicate path extracts content after attaching a PDF."""
        service, repo, resolver, _, library_root = setup_with_extraction
        meta = _make_metadata(doi_value="10.1234/mdonly")
        note_path = library_root / "S" / "Smith 2024 - Test Paper Title.md"
        note_path.parent.mkdir()
        note_path.write_text("metadata note", encoding="utf-8")
        paper = Paper.create(metadata=meta, note_path=str(note_path))
        repo._papers[paper.id] = paper
        resolver.set_response("10.1234/mdonly", meta)
        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "paper.pdf")

        with (
            patch("src.application.import_service.extract_doi_from_pdf") as mock_doi,
            patch.object(service, "_extract_and_append_content") as mock_extract,
        ):
            mock_doi.return_value = DOI("10.1234/mdonly")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        assert result.paper is not None
        mock_extract.assert_called_once_with(str(pdf_path), result.paper)

    def test_appends_extracted_body_to_md(
        self,
        setup_with_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """When extraction succeeds, body is appended to MD after separator."""
        service, repo, resolver, _, library_root = setup_with_extraction

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        extraction_result = ExtractionResult(
            body_markdown="# Introduction\n\nThis paper explores...",
            figures=[],
        )

        with (
            patch("src.application.import_service.extract_doi_from_pdf") as mock_doi,
            patch("src.application.import_service.extract_pdf_content") as mock_extract,
        ):
            mock_doi.return_value = DOI("10.1234/test.001")
            mock_extract.return_value = extraction_result
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"

        # Read the MD file and check content
        paper = result.paper
        assert paper is not None
        assert paper.note_path is not None
        md_content = Path(paper.note_path).read_text(encoding="utf-8")
        assert "---" in md_content  # Separator
        assert "# Introduction" in md_content
        assert "This paper explores..." in md_content

    def test_saves_figures_and_adds_references(
        self,
        setup_with_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """Extracted figures are saved and referenced in MD."""
        service, repo, resolver, _, library_root = setup_with_extraction

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        fig = ExtractedFigure(
            image_bytes=b"fake-png-data",
            filename="figure-1.png",
            alt_text="Architecture diagram",
            source_index=1,
        )
        extraction_result = ExtractionResult(
            body_markdown="# Results\n\nSee figure below.\n\n<!-- image -->",
            figures=[fig],
        )

        with (
            patch("src.application.import_service.extract_doi_from_pdf") as mock_doi,
            patch("src.application.import_service.extract_pdf_content") as mock_extract,
        ):
            mock_doi.return_value = DOI("10.1234/test.001")
            mock_extract.return_value = extraction_result
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        paper = result.paper
        assert paper is not None
        assert paper.note_path is not None

        # Check MD contains figure reference
        md_content = Path(paper.note_path).read_text(encoding="utf-8")
        assert "![Architecture diagram]" in md_content
        assert "figure-1.png" in md_content

        # Check figure file was saved
        note_dir = Path(paper.note_path).parent
        file_name = paper.build_file_name()
        assets_dir = note_dir / f"{file_name.value}.assets"
        assert assets_dir.exists()
        assert (assets_dir / "figure-1.png").exists()
        assert (assets_dir / "figure-1.png").read_bytes() == b"fake-png-data"

    def test_extraction_failure_still_succeeds(
        self,
        setup_with_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """If content extraction fails, import still succeeds with metadata MD."""
        service, repo, resolver, _, library_root = setup_with_extraction

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        # Extraction returns failure
        extraction_result = ExtractionResult(
            error_message="Docling model not found",
        )

        with (
            patch("src.application.import_service.extract_doi_from_pdf") as mock_doi,
            patch("src.application.import_service.extract_pdf_content") as mock_extract,
        ):
            mock_doi.return_value = DOI("10.1234/test.001")
            mock_extract.return_value = extraction_result
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"

        # MD should still exist but without body content
        paper = result.paper
        assert paper is not None
        assert paper.note_path is not None
        md_content = Path(paper.note_path).read_text(encoding="utf-8")
        # Should have frontmatter but not the body separator followed by content
        assert "Test Paper Title" in md_content

    def test_extraction_exception_still_succeeds(
        self,
        setup_with_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """If extract_pdf_content raises, import still succeeds."""
        service, repo, resolver, _, library_root = setup_with_extraction

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        with (
            patch("src.application.import_service.extract_doi_from_pdf") as mock_doi,
            patch("src.application.import_service.extract_pdf_content") as mock_extract,
        ):
            mock_doi.return_value = DOI("10.1234/test.001")
            mock_extract.side_effect = RuntimeError("Total failure")
            result = service.handle_new_pdf(str(pdf_path))

        # Import still succeeds
        assert result.status == "success"


# ============================================================
# Tests: Full text extraction disabled
# ============================================================


class TestImportWithoutContentExtraction:
    """Tests for import pipeline with full text extraction disabled."""

    def test_extraction_not_called_when_disabled(
        self,
        setup_without_extraction: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        """When extract_full_text=False, Docling is never called."""
        service, repo, resolver, _, library_root = setup_without_extraction

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        with (
            patch("src.application.import_service.extract_doi_from_pdf") as mock_doi,
            patch("src.application.import_service.extract_pdf_content") as mock_extract,
        ):
            mock_doi.return_value = DOI("10.1234/test.001")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        mock_extract.assert_not_called()
