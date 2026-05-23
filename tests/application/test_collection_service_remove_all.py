"""Tests for CollectionAppService.remove_paper_from_all_collections.

Uses mocked repositories to isolate from filesystem.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.application.collection_service import CollectionAppService
from src.domain.collection import Collection, CollectionId, PaperRef
from src.domain.paper import PaperId
from src.domain.ports import CollectionRepository, PaperRepository

# ============================================================
# Helpers
# ============================================================


def _make_collection(
    collection_id: str,
    name: str,
    paper_ids: list[str] | None = None,
) -> Collection:
    """Create a Collection with optional paper references."""
    coll = Collection(id=CollectionId(collection_id), name=name)
    for pid_str in paper_ids or []:
        coll.add_paper(PaperRef(paper_id=PaperId(pid_str)))
    return coll


# ============================================================
# Tests
# ============================================================


class TestRemovePaperFromAllCollections:
    """Tests for CollectionAppService.remove_paper_from_all_collections."""

    def test_removes_from_single_collection(self) -> None:
        """Paper reference is removed from the one collection containing it."""
        target_paper_id = "10.1234/test.001"
        coll = _make_collection("coll-1", "My Collection", [target_paper_id])

        collection_repo = MagicMock(spec=CollectionRepository)
        collection_repo.find_all.return_value = [coll]
        paper_repo = MagicMock(spec=PaperRepository)

        service = CollectionAppService(collection_repo, paper_repo)
        modified = service.remove_paper_from_all_collections(target_paper_id)

        assert modified == 1
        collection_repo.save.assert_called_once()
        # Verify the paper ref was actually removed from the collection
        assert not coll.contains(PaperRef(paper_id=PaperId(target_paper_id)))

    def test_removes_from_multiple_collections(self) -> None:
        """Paper reference is removed from all collections that contain it."""
        target_paper_id = "10.1234/test.001"
        coll1 = _make_collection(
            "coll-1", "Collection A", [target_paper_id, "10.5678/other"]
        )
        coll2 = _make_collection("coll-2", "Collection B", [target_paper_id])
        coll3 = _make_collection("coll-3", "Collection C", ["10.9999/unrelated"])

        collection_repo = MagicMock(spec=CollectionRepository)
        collection_repo.find_all.return_value = [coll1, coll2, coll3]
        paper_repo = MagicMock(spec=PaperRepository)

        service = CollectionAppService(collection_repo, paper_repo)
        modified = service.remove_paper_from_all_collections(target_paper_id)

        assert modified == 2
        assert collection_repo.save.call_count == 2

    def test_no_collections_contain_paper(self) -> None:
        """Returns 0 when no collection references the paper."""
        coll = _make_collection("coll-1", "Empty Coll", ["10.5678/other"])

        collection_repo = MagicMock(spec=CollectionRepository)
        collection_repo.find_all.return_value = [coll]
        paper_repo = MagicMock(spec=PaperRepository)

        service = CollectionAppService(collection_repo, paper_repo)
        modified = service.remove_paper_from_all_collections("10.9999/nonexistent")

        assert modified == 0
        collection_repo.save.assert_not_called()

    def test_empty_collection_list(self) -> None:
        """Returns 0 when there are no collections at all."""
        collection_repo = MagicMock(spec=CollectionRepository)
        collection_repo.find_all.return_value = []
        paper_repo = MagicMock(spec=PaperRepository)

        service = CollectionAppService(collection_repo, paper_repo)
        modified = service.remove_paper_from_all_collections("10.1234/test.001")

        assert modified == 0

    def test_other_papers_in_collection_preserved(self) -> None:
        """Other paper references in the collection remain intact."""
        target = "10.1234/test.001"
        other = "10.5678/test.002"
        coll = _make_collection("coll-1", "Mixed", [target, other])

        collection_repo = MagicMock(spec=CollectionRepository)
        collection_repo.find_all.return_value = [coll]
        paper_repo = MagicMock(spec=PaperRepository)

        service = CollectionAppService(collection_repo, paper_repo)
        service.remove_paper_from_all_collections(target)

        assert not coll.contains(PaperRef(paper_id=PaperId(target)))
        assert coll.contains(PaperRef(paper_id=PaperId(other)))
