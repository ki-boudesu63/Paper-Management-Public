"""Tests for LibraryAppService (listing, search, detail retrieval)."""

from __future__ import annotations

import pytest

from src.application.library_service import LibraryAppService, SearchQuery
from src.domain.paper import (
    DOI,
    Author,
    InitialLetter,
    Metadata,
    Paper,
    PaperId,
    PublicationYear,
)
from src.domain.ports import PaperRepository

# ============================================================
# Mock Repository
# ============================================================


class MockPaperRepository(PaperRepository):
    """In-memory mock PaperRepository for testing."""

    def __init__(self, papers: list[Paper] | None = None) -> None:
        self._papers: dict[PaperId, Paper] = {}
        self._scan_called = False
        if papers:
            for p in papers:
                self._papers[p.id] = p

    def find_by_id(self, paper_id: PaperId) -> Paper | None:
        return self._papers.get(paper_id)

    def find_all(self) -> list[Paper]:
        return list(self._papers.values())

    def save(self, paper: Paper) -> None:
        self._papers[paper.id] = paper

    def delete(self, paper_id: PaperId) -> None:
        if paper_id not in self._papers:
            raise KeyError(f"Not found: {paper_id.value}")
        del self._papers[paper_id]

    def scan(self) -> None:
        self._scan_called = True

    @property
    def scan_called(self) -> bool:
        return self._scan_called


# ============================================================
# Helpers
# ============================================================


def _make_paper(
    doi_value: str = "10.1234/test",
    title: str = "Test Paper",
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    tags: list[str] | None = None,
    initial: str | None = None,
    abstract: str = "",
    memo: str = "",
) -> Paper:
    """Create a Paper for testing."""
    doi = DOI(doi_value)
    meta = Metadata(
        title=title,
        authors=(Author(family_name=family, given_name=given),),
        year=PublicationYear(year),
        doi=doi,
        abstract=abstract,
        memo=memo,
    )
    paper = Paper(
        id=PaperId.from_doi(doi),
        metadata=meta,
        pdf_path=f"/fake/{family}_{year}.pdf",
        note_path=f"/fake/{family}_{year}.md",
        initial_letter=InitialLetter(initial if initial else family[0].upper()),
        tags=tags or [],
    )
    return paper


# ============================================================
# Tests: Initialization
# ============================================================


class TestLibraryServiceInit:
    """Tests for LibraryAppService initialization."""

    def test_initialize_calls_scan(self) -> None:
        repo = MockPaperRepository()
        service = LibraryAppService(repo)
        service.initialize()
        assert repo.scan_called


# ============================================================
# Tests: list_all
# ============================================================


class TestLibraryServiceListAll:
    """Tests for listing all papers."""

    def test_list_all_empty(self) -> None:
        repo = MockPaperRepository()
        service = LibraryAppService(repo)
        assert service.list_all() == []

    def test_list_all_returns_papers(self) -> None:
        papers = [
            _make_paper(doi_value="10.1234/a", family="Alpha"),
            _make_paper(doi_value="10.1234/b", family="Beta"),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        result = service.list_all()
        assert len(result) == 2

    def test_list_all_sorted_by_author(self) -> None:
        papers = [
            _make_paper(doi_value="10.1234/z", family="Zeta"),
            _make_paper(doi_value="10.1234/a", family="Alpha"),
            _make_paper(doi_value="10.1234/m", family="Mu"),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        result = service.list_all()
        names = [p.metadata.first_author.family_name for p in result]
        assert names == ["Alpha", "Mu", "Zeta"]


# ============================================================
# Tests: get_by_id
# ============================================================


class TestLibraryServiceGetById:
    """Tests for retrieving a paper by ID."""

    def test_get_existing_paper(self) -> None:
        paper = _make_paper(doi_value="10.1234/found")
        repo = MockPaperRepository([paper])
        service = LibraryAppService(repo)
        result = service.get_by_id(paper.id)
        assert result is not None
        assert result.id == paper.id

    def test_get_nonexistent_paper(self) -> None:
        repo = MockPaperRepository()
        service = LibraryAppService(repo)
        result = service.get_by_id(PaperId("10.9999/missing"))
        assert result is None


# ============================================================
# Tests: search
# ============================================================


class TestLibraryServiceSearch:
    """Tests for lightweight metadata search."""

    @pytest.fixture()
    def service_with_papers(self) -> LibraryAppService:
        papers = [
            _make_paper(
                doi_value="10.1234/a",
                title="Cell Biology Advances",
                family="Tanaka",
                year=2023,
                tags=["biology", "cell"],
            ),
            _make_paper(
                doi_value="10.1234/b",
                title="Machine Learning Methods",
                family="Smith",
                year=2024,
                tags=["ml", "ai"],
            ),
            _make_paper(
                doi_value="10.1234/c",
                title="Quantum Physics Review",
                family="Tanaka",
                year=2024,
                tags=["physics"],
            ),
        ]
        repo = MockPaperRepository(papers)
        return LibraryAppService(repo)

    def test_search_by_author(self, service_with_papers: LibraryAppService) -> None:
        results = service_with_papers.search(SearchQuery(author="Tanaka"))
        assert len(results) == 2
        for p in results:
            assert p.metadata.first_author.family_name == "Tanaka"

    def test_search_by_author_case_insensitive(
        self, service_with_papers: LibraryAppService
    ) -> None:
        results = service_with_papers.search(SearchQuery(author="tanaka"))
        assert len(results) == 2

    def test_search_by_year(self, service_with_papers: LibraryAppService) -> None:
        results = service_with_papers.search(SearchQuery(year=2024))
        assert len(results) == 2

    def test_search_by_tag(self, service_with_papers: LibraryAppService) -> None:
        results = service_with_papers.search(SearchQuery(tag="biology"))
        assert len(results) == 1
        assert results[0].metadata.title == "Cell Biology Advances"

    def test_search_by_title(self, service_with_papers: LibraryAppService) -> None:
        results = service_with_papers.search(SearchQuery(title="Quantum"))
        assert len(results) == 1
        assert "Quantum" in results[0].metadata.title

    def test_search_combined_author_and_year(
        self, service_with_papers: LibraryAppService
    ) -> None:
        results = service_with_papers.search(SearchQuery(author="Tanaka", year=2024))
        assert len(results) == 1
        assert results[0].metadata.title == "Quantum Physics Review"

    def test_search_no_results(self, service_with_papers: LibraryAppService) -> None:
        results = service_with_papers.search(SearchQuery(author="Nobody"))
        assert len(results) == 0

    def test_search_empty_query_returns_all(
        self, service_with_papers: LibraryAppService
    ) -> None:
        results = service_with_papers.search(SearchQuery())
        assert len(results) == 3

    def test_search_results_sorted(
        self, service_with_papers: LibraryAppService
    ) -> None:
        results = service_with_papers.search(SearchQuery(year=2024))
        names = [p.metadata.first_author.family_name for p in results]
        assert names == sorted(names, key=str.lower)

    def test_search_by_given_name(self, service_with_papers: LibraryAppService) -> None:
        results = service_with_papers.search(SearchQuery(author="John"))
        # All test papers have given_name "John"
        assert len(results) == 3

    def test_search_by_tag_case_insensitive(
        self, service_with_papers: LibraryAppService
    ) -> None:
        results = service_with_papers.search(SearchQuery(tag="ML"))
        assert len(results) == 1


# ============================================================
# Tests: list_by_initial
# ============================================================


class TestLibraryServiceListByInitial:
    """Tests for filtering papers by initial letter."""

    def test_list_by_initial_letter(self) -> None:
        papers = [
            _make_paper(doi_value="10.1234/a", family="Alpha", initial="A"),
            _make_paper(doi_value="10.1234/b", family="Beta", initial="B"),
            _make_paper(doi_value="10.1234/c", family="Aaronson", initial="A"),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        result = service.list_by_initial("A")
        assert len(result) == 2

    def test_list_by_initial_hash(self) -> None:
        papers = [
            _make_paper(doi_value="10.1234/x", family="Alpha", initial="A"),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        result = service.list_by_initial("#")
        assert len(result) == 0

    def test_list_by_initial_case_insensitive(self) -> None:
        papers = [
            _make_paper(doi_value="10.1234/a", family="Alpha", initial="A"),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        result = service.list_by_initial("a")
        assert len(result) == 1


# ============================================================
# Tests: fulltext_search (cross-field AND search)
# ============================================================


class TestFulltextSearch:
    """Tests for cross-field free-text AND search."""

    @pytest.fixture()
    def service(self) -> LibraryAppService:
        """Service with diverse papers for fulltext search testing."""
        papers = [
            _make_paper(
                doi_value="10.1234/ft1",
                title="iPS Cell Reprogramming Methods",
                family="Okita",
                given="Keisuke",
                year=2023,
                tags=["ips", "reprogramming"],
                abstract="Efficient generation of iPS cells from blood.",
                memo="Key reference for the project.",
            ),
            _make_paper(
                doi_value="10.1234/ft2",
                title="Tracheal Regeneration with Stem Cells",
                family="Tanaka",
                given="Yuki",
                year=2024,
                tags=["trachea", "regeneration"],
                abstract="We explored tracheal cartilage scaffolds.",
                memo="Discussed at lab meeting 2024-01.",
            ),
            _make_paper(
                doi_value="10.1234/ft3",
                title="Machine Learning in Drug Discovery",
                family="Smith",
                given="Alice",
                year=2025,
                tags=["ml", "drug-discovery"],
                abstract="Deep learning models predict binding affinity.",
                memo="",
            ),
            _make_paper(
                doi_value="10.1234/ft4",
                title="Quantum Computing Overview",
                family="Chen",
                given="Wei",
                year=2024,
                tags=["quantum"],
            ),
        ]
        repo = MockPaperRepository(papers)
        return LibraryAppService(repo)

    # -- Single term tests --

    def test_single_term_title_match(self, service: LibraryAppService) -> None:
        """Single term matching title."""
        results = service.fulltext_search("Tracheal")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Tanaka"

    def test_single_term_author_family_match(self, service: LibraryAppService) -> None:
        """Single term matching author family name."""
        results = service.fulltext_search("Okita")
        assert len(results) == 1
        assert results[0].metadata.title == "iPS Cell Reprogramming Methods"

    def test_single_term_author_given_match(self, service: LibraryAppService) -> None:
        """Single term matching author given name."""
        results = service.fulltext_search("Alice")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Smith"

    def test_single_term_abstract_match(self, service: LibraryAppService) -> None:
        """Single term matching abstract field."""
        results = service.fulltext_search("scaffolds")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Tanaka"

    def test_single_term_memo_match(self, service: LibraryAppService) -> None:
        """Single term matching memo field."""
        results = service.fulltext_search("project")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Okita"

    def test_single_term_year_match(self, service: LibraryAppService) -> None:
        """Single term matching year (stringified)."""
        results = service.fulltext_search("2025")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Smith"

    def test_single_term_tag_match(self, service: LibraryAppService) -> None:
        """Single term matching a tag."""
        results = service.fulltext_search("quantum")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Chen"

    # -- Multi-term AND tests --

    def test_multi_term_and_both_match(self, service: LibraryAppService) -> None:
        """Multiple terms: both must match (different fields)."""
        # "Okita" matches author, "iPS" matches title/abstract/tag
        results = service.fulltext_search("Okita iPS")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Okita"

    def test_multi_term_and_one_fails(self, service: LibraryAppService) -> None:
        """Multiple terms: one term does not match -> no results."""
        # "Okita" matches first paper, "tracheal" matches second paper
        results = service.fulltext_search("Okita tracheal")
        assert len(results) == 0

    def test_multi_term_cross_field(self, service: LibraryAppService) -> None:
        """Terms matched from different fields of the same paper."""
        # "Tanaka" is author, "2024" is year, "scaffolds" is abstract
        results = service.fulltext_search("Tanaka 2024 scaffolds")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Tanaka"

    # -- Case insensitivity --

    def test_case_insensitive_title(self, service: LibraryAppService) -> None:
        """Search is case-insensitive for title."""
        results = service.fulltext_search("MACHINE LEARNING")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Smith"

    def test_case_insensitive_author(self, service: LibraryAppService) -> None:
        """Search is case-insensitive for author."""
        results = service.fulltext_search("okita")
        assert len(results) == 1

    def test_case_insensitive_tag(self, service: LibraryAppService) -> None:
        """Search is case-insensitive for tag."""
        results = service.fulltext_search("IPS")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Okita"

    # -- Empty / whitespace queries --

    def test_empty_query_returns_all(self, service: LibraryAppService) -> None:
        """Empty string returns all papers."""
        results = service.fulltext_search("")
        assert len(results) == 4

    def test_whitespace_only_returns_all(self, service: LibraryAppService) -> None:
        """Whitespace-only string returns all papers."""
        results = service.fulltext_search("   ")
        assert len(results) == 4

    # -- None-safe fields --

    def test_none_abstract_safe(self) -> None:
        """Papers with empty abstract do not cause errors."""
        papers = [
            _make_paper(
                doi_value="10.1234/none1",
                title="No Abstract Paper",
                family="NoAbstract",
                year=2024,
            ),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        # Should not raise, and should not match
        results = service.fulltext_search("scaffolds")
        assert len(results) == 0

    def test_none_memo_safe(self) -> None:
        """Papers with empty memo do not cause errors."""
        papers = [
            _make_paper(
                doi_value="10.1234/none2",
                title="No Memo Paper",
                family="NoMemo",
                year=2024,
                memo="",
            ),
        ]
        repo = MockPaperRepository(papers)
        service = LibraryAppService(repo)
        results = service.fulltext_search("meeting")
        assert len(results) == 0

    # -- Sorted results --

    def test_results_sorted_by_author(self, service: LibraryAppService) -> None:
        """Results are sorted by first author family name."""
        # "2024" matches Tanaka (year) and Chen (year)
        results = service.fulltext_search("2024")
        assert len(results) == 2
        names = [p.metadata.first_author.family_name for p in results]
        assert names == sorted(names, key=str.lower)

    # -- Partial match --

    def test_partial_term_match(self, service: LibraryAppService) -> None:
        """Partial substring matching works."""
        # "regen" is a substring of "Regeneration" (title) and "regeneration" (tag)
        results = service.fulltext_search("regen")
        assert len(results) == 1
        assert results[0].metadata.first_author.family_name == "Tanaka"

    # -- Year partial match --

    def test_year_partial_match(self, service: LibraryAppService) -> None:
        """Partial year match: '202' matches all papers with 202x years."""
        results = service.fulltext_search("202")
        assert len(results) == 4
