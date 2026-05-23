"""Tests for ImportAppService (paper import pipeline)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.application.import_service import ImportAppService
from src.application.metadata_buffer import MetadataBuffer
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

    def __init__(self) -> None:
        self._papers: dict[PaperId, Paper] = {}
        self._scan_called = False

    def find_by_id(self, paper_id: PaperId) -> Paper | None:
        return self._papers.get(paper_id)

    def find_all(self) -> list[Paper]:
        return list(self._papers.values())

    def save(self, paper: Paper) -> None:
        self._papers[paper.id] = paper

    def attach_pdf(self, paper_id: PaperId, pdf_path: str) -> Paper:
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

    @property
    def scan_called(self) -> bool:
        return self._scan_called


class MockMetadataResolver(MetadataResolver):
    """Mock MetadataResolver for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, Metadata | None] = {}

    def set_response(self, doi_value: str, metadata: Metadata | None) -> None:
        self._responses[doi_value] = metadata

    def resolve(self, doi: DOI) -> Metadata | None:
        return self._responses.get(doi.value)


@pytest.fixture()
def setup(
    tmp_path: Path,
) -> tuple[
    ImportAppService,
    MockPaperRepository,
    MockMetadataResolver,
    MetadataBuffer,
    Path,
]:
    """Create a fully wired ImportAppService with mocks."""
    library_root = tmp_path / "library"
    library_root.mkdir()

    repo = MockPaperRepository()
    resolver = MockMetadataResolver()
    buffer = MetadataBuffer()

    service = ImportAppService(
        paper_repo=repo,
        metadata_resolver=resolver,
        metadata_buffer=buffer,
        library_root=library_root,
        unsorted_folder_name="unsorted",
    )

    return service, repo, resolver, buffer, library_root


# ============================================================
# Tests: Initialization
# ============================================================


class TestImportServiceInit:
    """Tests for ImportAppService initialization."""

    def test_initialize_calls_repo_scan(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, _, _, _ = setup
        service.initialize()
        assert repo.scan_called

    def test_empty_import_history(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, _, _, _ = setup
        assert service.import_history == []


# ============================================================
# Tests: Happy path - DOI extraction + CrossRef
# ============================================================


class TestImportServiceHappyPath:
    """Tests for successful import pipeline."""

    def test_import_with_doi_from_crossref(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, resolver, _, library_root = setup

        # Create test PDF
        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        # Set up CrossRef to return metadata
        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/test.001")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        assert result.paper is not None
        assert result.paper.metadata.title == "Test Paper Title"
        assert len(repo.find_all()) == 1

    def test_import_result_in_history(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, resolver, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/test.001")
            service.handle_new_pdf(str(pdf_path))

        assert len(service.import_history) == 1
        assert service.import_history[0].status == "success"


# ============================================================
# Tests: Buffer lookup
# ============================================================


class TestImportServiceBuffer:
    """Tests for Chrome extension metadata buffer integration."""

    def test_import_uses_buffer_by_doi(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, resolver, buffer, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        # Pre-buffer metadata from Chrome extension
        meta = _make_metadata(title="Buffered Paper")
        buffer.put(meta)

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/test.001")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        assert result.paper is not None
        assert result.paper.metadata.title == "Buffered Paper"

    def test_receive_extension_metadata_buffers_it(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, _, buffer, _ = setup
        meta = _make_metadata(title="Extension Data")
        service.receive_extension_metadata(meta)
        assert buffer.lookup_by_doi("10.1234/test.001") is not None

    def test_register_metadata_only_creates_md_only_paper_from_crossref(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, resolver, _, _ = setup
        payload_meta = _make_metadata(
            title="Extension Title",
            family="Smith",
            doi_value="10.1234/mdonly",
        )
        crossref_meta = _make_metadata(
            title="CrossRef Completed Title",
            family="Jones",
            doi_value="10.1234/mdonly",
        )
        resolver.set_response("10.1234/mdonly", crossref_meta)

        result = service.register_metadata_only(payload_meta)

        assert result.status == "success"
        assert result.paper is not None
        assert result.paper.metadata.title == "CrossRef Completed Title"
        assert not result.paper.has_pdf
        assert repo.find_by_id(PaperId("10.1234/mdonly")) is not None

    def test_import_uses_buffer_by_author_year(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, _, buffer, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        # Filename in Paperpile format: "Tanaka 2023 - Some Title.pdf"
        pdf_path = _create_test_pdf(watch_dir / "Tanaka 2023 - Some Title.pdf")

        # Buffer has metadata matching author/year
        meta = _make_metadata(
            title="Tanaka Research",
            family="Tanaka",
            year=2023,
            doi_value="10.1234/tanaka",
        )
        buffer.put(meta)

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = None  # No DOI in PDF
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        assert result.paper is not None
        assert result.paper.metadata.first_author.family_name == "Tanaka"


# ============================================================
# Tests: Duplicate detection
# ============================================================


class TestImportServiceDuplicate:
    """Tests for duplicate paper detection."""

    def test_duplicate_paper_skipped(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, resolver, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()

        meta = _make_metadata()
        resolver.set_response("10.1234/test.001", meta)

        # Import first copy
        pdf1 = _create_test_pdf(watch_dir / "first.pdf")
        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/test.001")
            result1 = service.handle_new_pdf(str(pdf1))
        assert result1.status == "success"

        # Import second copy (same DOI)
        pdf2 = _create_test_pdf(watch_dir / "second.pdf")
        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/test.001")
            result2 = service.handle_new_pdf(str(pdf2))

        assert result2.status == "duplicate"
        assert len(repo.find_all()) == 1

    def test_new_pdf_with_existing_md_only_paper_attaches_pdf(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, resolver, _, library_root = setup
        meta = _make_metadata(doi_value="10.1234/mdonly")
        md_only = Paper.create(metadata=meta)
        repo.save(md_only)
        resolver.set_response("10.1234/mdonly", meta)
        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "paper.pdf")

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/mdonly")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "success"
        assert result.paper is not None
        assert result.paper.has_pdf
        assert result.paper.pdf_path == str(pdf_path)
        assert len(repo.find_all()) == 1


# ============================================================
# Tests: Unsorted fallback
# ============================================================


class TestImportServiceUnsorted:
    """Tests for unsorted folder fallback on metadata failure."""

    def test_no_metadata_moves_to_unsorted(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, repo, _, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "unknown.pdf")

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = None
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "unsorted"
        assert "unsorted" in result.message.lower() or "Moved to" in result.message

        # PDF should have been moved
        unsorted_dir = library_root / "unsorted"
        assert unsorted_dir.exists()
        unsorted_files = list(unsorted_dir.glob("*.pdf"))
        assert len(unsorted_files) == 1

    def test_unsorted_handles_name_collision(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, _, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()

        # Pre-create a file in unsorted with the same name
        unsorted_dir = library_root / "unsorted"
        unsorted_dir.mkdir()
        (unsorted_dir / "dup.pdf").write_bytes(b"existing")

        pdf_path = _create_test_pdf(watch_dir / "dup.pdf")

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = None
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "unsorted"
        # Should have created dup_1.pdf
        unsorted_files = sorted(unsorted_dir.glob("*.pdf"))
        assert len(unsorted_files) == 2

    def test_crossref_failure_moves_to_unsorted(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, resolver, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        # DOI found but CrossRef returns None
        resolver.set_response("10.1234/fail", None)

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = DOI("10.1234/fail")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "unsorted"


# ============================================================
# Tests: Error handling
# ============================================================


class TestImportServiceErrors:
    """Tests for error handling in the import pipeline."""

    def test_nonexistent_pdf_returns_error(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, _, _, _ = setup
        result = service.handle_new_pdf("/nonexistent/path/paper.pdf")
        assert result.status == "error"
        assert "does not exist" in result.message

    def test_unexpected_exception_caught(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, _, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()
        pdf_path = _create_test_pdf(watch_dir / "test.pdf")

        with patch(
            "src.application.import_service.extract_doi_from_pdf"
        ) as mock_extract:
            mock_extract.side_effect = RuntimeError("Unexpected crash")
            result = service.handle_new_pdf(str(pdf_path))

        assert result.status == "error"
        assert "Unexpected crash" in result.message

    def test_multiple_imports_tracked_in_history(
        self,
        setup: tuple[
            ImportAppService,
            MockPaperRepository,
            MockMetadataResolver,
            MetadataBuffer,
            Path,
        ],
    ) -> None:
        service, _, _, _, library_root = setup

        watch_dir = library_root.parent / "watch"
        watch_dir.mkdir()

        # Import two files (both will fail -> unsorted)
        for name in ("a.pdf", "b.pdf"):
            pdf_path = _create_test_pdf(watch_dir / name)
            with patch(
                "src.application.import_service.extract_doi_from_pdf"
            ) as mock_extract:
                mock_extract.return_value = None
                service.handle_new_pdf(str(pdf_path))

        assert len(service.import_history) == 2
