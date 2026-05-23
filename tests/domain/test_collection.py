"""Tests for Collection domain entity and PaperRef value object.

Covers happy path, boundary values, and error cases.
"""

from __future__ import annotations

import pytest

from src.domain.collection import Collection, CollectionId, PaperRef
from src.domain.paper import PaperId

# ============================================================
# PaperRef Value Object
# ============================================================


class TestPaperRef:
    """Tests for PaperRef value object."""

    def test_create_valid_ref(self) -> None:
        ref = PaperRef(paper_id=PaperId("10.1234/test"))
        assert ref.paper_id.value == "10.1234/test"

    def test_equality(self) -> None:
        ref1 = PaperRef(paper_id=PaperId("10.1234/test"))
        ref2 = PaperRef(paper_id=PaperId("10.1234/test"))
        assert ref1 == ref2

    def test_inequality(self) -> None:
        ref1 = PaperRef(paper_id=PaperId("10.1234/a"))
        ref2 = PaperRef(paper_id=PaperId("10.1234/b"))
        assert ref1 != ref2

    def test_hashable(self) -> None:
        ref = PaperRef(paper_id=PaperId("10.1234/test"))
        ref_set = {ref}
        assert PaperRef(paper_id=PaperId("10.1234/test")) in ref_set


# ============================================================
# CollectionId
# ============================================================


class TestCollectionId:
    """Tests for CollectionId."""

    def test_create_valid_id(self) -> None:
        cid = CollectionId("my-project-2024")
        assert cid.value == "my-project-2024"

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id"):
            CollectionId("")

    def test_whitespace_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id"):
            CollectionId("   ")

    def test_equality(self) -> None:
        assert CollectionId("abc") == CollectionId("abc")

    def test_inequality(self) -> None:
        assert CollectionId("abc") != CollectionId("def")

    def test_hashable(self) -> None:
        cid = CollectionId("test")
        cid_set = {cid}
        assert CollectionId("test") in cid_set


# ============================================================
# Collection Entity
# ============================================================


class TestCollection:
    """Tests for Collection entity."""

    @pytest.fixture()
    def empty_collection(self) -> Collection:
        return Collection(
            id=CollectionId("thesis-2024"),
            name="Thesis 2024",
        )

    @pytest.fixture()
    def sample_ref(self) -> PaperRef:
        return PaperRef(paper_id=PaperId("10.1234/paper1"))

    @pytest.fixture()
    def another_ref(self) -> PaperRef:
        return PaperRef(paper_id=PaperId("10.1234/paper2"))

    def test_create_collection(self, empty_collection: Collection) -> None:
        assert empty_collection.id.value == "thesis-2024"
        assert empty_collection.name == "Thesis 2024"
        assert len(empty_collection.paper_refs) == 0

    def test_add_paper(
        self, empty_collection: Collection, sample_ref: PaperRef
    ) -> None:
        empty_collection.add_paper(sample_ref)
        assert len(empty_collection.paper_refs) == 1
        assert empty_collection.contains(sample_ref)

    def test_add_duplicate_paper_ignored(
        self, empty_collection: Collection, sample_ref: PaperRef
    ) -> None:
        empty_collection.add_paper(sample_ref)
        empty_collection.add_paper(sample_ref)
        assert len(empty_collection.paper_refs) == 1

    def test_remove_paper(
        self, empty_collection: Collection, sample_ref: PaperRef
    ) -> None:
        empty_collection.add_paper(sample_ref)
        empty_collection.remove_paper(sample_ref)
        assert len(empty_collection.paper_refs) == 0
        assert not empty_collection.contains(sample_ref)

    def test_remove_nonexistent_paper_raises(
        self, empty_collection: Collection, sample_ref: PaperRef
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            empty_collection.remove_paper(sample_ref)

    def test_contains_false(
        self, empty_collection: Collection, sample_ref: PaperRef
    ) -> None:
        assert not empty_collection.contains(sample_ref)

    def test_contains_true(
        self, empty_collection: Collection, sample_ref: PaperRef
    ) -> None:
        empty_collection.add_paper(sample_ref)
        assert empty_collection.contains(sample_ref)

    def test_multiple_papers(
        self,
        empty_collection: Collection,
        sample_ref: PaperRef,
        another_ref: PaperRef,
    ) -> None:
        empty_collection.add_paper(sample_ref)
        empty_collection.add_paper(another_ref)
        assert len(empty_collection.paper_refs) == 2

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name"):
            Collection(
                id=CollectionId("test"),
                name="",
            )

    def test_whitespace_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name"):
            Collection(
                id=CollectionId("test"),
                name="   ",
            )

    def test_paper_count(
        self,
        empty_collection: Collection,
        sample_ref: PaperRef,
        another_ref: PaperRef,
    ) -> None:
        assert empty_collection.paper_count == 0
        empty_collection.add_paper(sample_ref)
        assert empty_collection.paper_count == 1
        empty_collection.add_paper(another_ref)
        assert empty_collection.paper_count == 2
