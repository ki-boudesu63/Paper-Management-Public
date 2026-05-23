"""Tests for CollectionAppService (collection CRUD operations)."""

from __future__ import annotations

import pytest

from src.application.collection_service import CollectionAppService
from src.domain.collection import Collection, CollectionId, PaperRef
from src.domain.paper import (
    DOI,
    Author,
    InitialLetter,
    Metadata,
    Paper,
    PaperId,
    PublicationYear,
)
from src.domain.ports import CollectionRepository, PaperRepository

# ============================================================
# Mock Repositories
# ============================================================


class MockCollectionRepository(CollectionRepository):
    """In-memory mock CollectionRepository."""

    def __init__(self) -> None:
        self._collections: dict[CollectionId, Collection] = {}

    def find_by_id(self, collection_id: CollectionId) -> Collection | None:
        return self._collections.get(collection_id)

    def find_all(self) -> list[Collection]:
        return list(self._collections.values())

    def save(self, collection: Collection) -> None:
        self._collections[collection.id] = collection

    def delete(self, collection_id: CollectionId) -> None:
        if collection_id not in self._collections:
            raise KeyError(f"Not found: {collection_id.value}")
        del self._collections[collection_id]


class MockPaperRepository(PaperRepository):
    """In-memory mock PaperRepository."""

    def __init__(self, papers: list[Paper] | None = None) -> None:
        self._papers: dict[PaperId, Paper] = {}
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
        del self._papers[paper_id]

    def scan(self) -> None:
        pass


# ============================================================
# Helpers
# ============================================================


def _make_paper(doi_value: str = "10.1234/test") -> Paper:
    """Create a test Paper."""
    doi = DOI(doi_value)
    meta = Metadata(
        title="Test Paper",
        authors=(Author(family_name="Smith"),),
        year=PublicationYear(2024),
        doi=doi,
    )
    return Paper(
        id=PaperId.from_doi(doi),
        metadata=meta,
        pdf_path="/fake/smith.pdf",
        note_path="/fake/smith.md",
        initial_letter=InitialLetter("S"),
    )


@pytest.fixture()
def service() -> tuple[
    CollectionAppService, MockCollectionRepository, MockPaperRepository
]:
    """Create a wired CollectionAppService with mocks."""
    paper = _make_paper()
    paper_repo = MockPaperRepository([paper])
    coll_repo = MockCollectionRepository()
    svc = CollectionAppService(
        collection_repo=coll_repo,
        paper_repo=paper_repo,
    )
    return svc, coll_repo, paper_repo


# ============================================================
# Tests: Create collection
# ============================================================


class TestCollectionServiceCreate:
    """Tests for creating collections."""

    def test_create_collection(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, coll_repo, _ = service
        coll = svc.create_collection("My Project")
        assert coll.name == "My Project"
        assert coll.paper_count == 0
        # Should be persisted
        assert coll_repo.find_by_id(coll.id) is not None

    def test_create_collection_empty_name_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        with pytest.raises(ValueError, match="name"):
            svc.create_collection("")

    def test_create_collection_whitespace_name_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        with pytest.raises(ValueError, match="name"):
            svc.create_collection("   ")

    def test_create_multiple_collections(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        c1 = svc.create_collection("Project A")
        c2 = svc.create_collection("Project B")
        assert c1.id != c2.id


# ============================================================
# Tests: List collections
# ============================================================


class TestCollectionServiceList:
    """Tests for listing collections."""

    def test_list_empty(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        assert svc.list_collections() == []

    def test_list_sorted_by_name(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        svc.create_collection("Zebra Project")
        svc.create_collection("Alpha Project")
        svc.create_collection("Mu Project")
        result = svc.list_collections()
        names = [c.name for c in result]
        assert names == ["Alpha Project", "Mu Project", "Zebra Project"]


# ============================================================
# Tests: Get collection
# ============================================================


class TestCollectionServiceGet:
    """Tests for getting a single collection."""

    def test_get_existing(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        coll = svc.create_collection("Test")
        result = svc.get_collection(coll.id.value)
        assert result is not None
        assert result.name == "Test"

    def test_get_nonexistent(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        result = svc.get_collection("nonexistent-id")
        assert result is None


# ============================================================
# Tests: Resolve collection papers
# ============================================================


class TestCollectionServiceListPapers:
    """Tests for resolving paper references inside collections."""

    def test_list_papers_in_collection_returns_referenced_papers(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        """Collection paper refs are resolved to Paper entities."""
        svc, _, _ = service
        coll = svc.create_collection("Test")
        paper_id = "10.1234/test"
        svc.add_paper_to_collection(coll.id.value, paper_id)

        papers = svc.list_papers_in_collection(coll.id.value)

        assert len(papers) == 1
        assert papers[0].id.value == paper_id

    def test_list_papers_in_collection_skips_stale_refs(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        """Stale PaperRef values do not break collection detail rendering."""
        svc, coll_repo, _ = service
        coll = svc.create_collection("Test")
        coll.add_paper(PaperRef(paper_id=PaperId("10.9999/missing")))
        coll_repo.save(coll)

        assert svc.list_papers_in_collection(coll.id.value) == []

    def test_list_papers_in_missing_collection_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        """A missing collection ID is reported as a KeyError."""
        svc, _, _ = service

        with pytest.raises(KeyError, match="Collection not found"):
            svc.list_papers_in_collection("missing")


class TestCollectionServicePaperMembership:
    """Tests for listing collection names containing a paper."""

    def test_list_collection_names_for_paper(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        """Collection names are returned sorted case-insensitively."""
        svc, _, _ = service
        paper_id = "10.1234/test"
        second = svc.create_collection("Zeta")
        first = svc.create_collection("Alpha")

        svc.add_paper_to_collection(second.id.value, paper_id)
        svc.add_paper_to_collection(first.id.value, paper_id)

        assert svc.list_collection_names_for_paper(paper_id) == ["Alpha", "Zeta"]


# ============================================================
# Tests: Add paper to collection
# ============================================================


class TestCollectionServiceAddPaper:
    """Tests for adding papers to collections."""

    def test_add_paper(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        coll = svc.create_collection("Test")
        paper_id = "10.1234/test"
        updated = svc.add_paper_to_collection(coll.id.value, paper_id)
        assert updated.paper_count == 1

    def test_add_paper_idempotent(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        coll = svc.create_collection("Test")
        paper_id = "10.1234/test"
        svc.add_paper_to_collection(coll.id.value, paper_id)
        updated = svc.add_paper_to_collection(coll.id.value, paper_id)
        assert updated.paper_count == 1

    def test_add_paper_nonexistent_collection_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        with pytest.raises(KeyError, match="Collection not found"):
            svc.add_paper_to_collection("no-such-collection", "10.1234/test")

    def test_add_nonexistent_paper_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        coll = svc.create_collection("Test")
        with pytest.raises(KeyError, match="Paper not found"):
            svc.add_paper_to_collection(coll.id.value, "10.9999/nope")


# ============================================================
# Tests: Remove paper from collection
# ============================================================


class TestCollectionServiceRemovePaper:
    """Tests for removing papers from collections."""

    def test_remove_paper(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        coll = svc.create_collection("Test")
        paper_id = "10.1234/test"
        svc.add_paper_to_collection(coll.id.value, paper_id)
        updated = svc.remove_paper_from_collection(coll.id.value, paper_id)
        assert updated.paper_count == 0

    def test_remove_nonexistent_paper_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        coll = svc.create_collection("Test")
        with pytest.raises(ValueError, match="not found"):
            svc.remove_paper_from_collection(coll.id.value, "10.1234/test")

    def test_remove_from_nonexistent_collection_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        with pytest.raises(KeyError, match="Collection not found"):
            svc.remove_paper_from_collection("no-such-id", "10.1234/test")


# ============================================================
# Tests: Delete collection
# ============================================================


class TestCollectionServiceDelete:
    """Tests for deleting collections."""

    def test_delete_collection(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, coll_repo, _ = service
        coll = svc.create_collection("To Delete")
        svc.delete_collection(coll.id.value)
        assert coll_repo.find_by_id(coll.id) is None

    def test_delete_nonexistent_raises(
        self,
        service: tuple[
            CollectionAppService, MockCollectionRepository, MockPaperRepository
        ],
    ) -> None:
        svc, _, _ = service
        with pytest.raises(KeyError, match="Collection not found"):
            svc.delete_collection("no-such-id")
