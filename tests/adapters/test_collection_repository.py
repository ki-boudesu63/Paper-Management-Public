"""Tests for FilesystemCollectionRepository.

Uses pytest tmp_path fixture for isolated filesystem operations.
Covers happy path, boundary values, and error cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.filesystem.collection_repository import (
    FilesystemCollectionRepository,
)
from src.domain.collection import Collection, CollectionId, PaperRef
from src.domain.paper import PaperId

# ============================================================
# Fixtures
# ============================================================


def _setup_library(tmp_path: Path) -> Path:
    """Create a library root with .collections/ directory."""
    library_root = tmp_path / "library"
    library_root.mkdir()
    return library_root


def _make_collection(
    coll_id: str = "proj-alpha",
    name: str = "Project Alpha",
    paper_ids: list[str] | None = None,
) -> Collection:
    """Helper to build a Collection."""
    coll = Collection(id=CollectionId(coll_id), name=name)
    if paper_ids:
        for pid in paper_ids:
            coll.add_paper(PaperRef(paper_id=PaperId(pid)))
    return coll


# ============================================================
# Construction / Initialization
# ============================================================


class TestFilesystemCollectionRepositoryInit:
    """Tests for repository initialization."""

    def test_init_creates_collections_dir(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        FilesystemCollectionRepository(library_root)
        assert (library_root / ".collections").is_dir()

    def test_init_with_nonexistent_root_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            FilesystemCollectionRepository(nonexistent)

    def test_find_all_empty(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)
        assert repo.find_all() == []


# ============================================================
# save + find_by_id
# ============================================================


class TestSaveAndFind:
    """Tests for save and find_by_id methods."""

    def test_save_creates_yaml_file(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection()
        repo.save(coll)

        yaml_path = library_root / ".collections" / "proj-alpha.yaml"
        assert yaml_path.exists()

    def test_find_by_id_returns_saved_collection(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection(paper_ids=["10.1234/paper.001", "10.1234/paper.002"])
        repo.save(coll)

        found = repo.find_by_id(CollectionId("proj-alpha"))
        assert found is not None
        assert found.name == "Project Alpha"
        assert found.paper_count == 2

    def test_find_by_id_nonexistent_returns_none(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        found = repo.find_by_id(CollectionId("nonexistent"))
        assert found is None

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection(paper_ids=["10.1234/paper.001"])
        repo.save(coll)

        # Update collection
        coll.add_paper(PaperRef(paper_id=PaperId("10.1234/paper.002")))
        repo.save(coll)

        found = repo.find_by_id(CollectionId("proj-alpha"))
        assert found is not None
        assert found.paper_count == 2

    def test_roundtrip_preserves_data(self, tmp_path: Path) -> None:
        """Save, then create new repo instance and load."""
        library_root = _setup_library(tmp_path)

        coll = _make_collection(
            coll_id="my-project",
            name="My Research Project",
            paper_ids=["10.1234/a", "sha256:abcdef1234567890"],
        )

        repo1 = FilesystemCollectionRepository(library_root)
        repo1.save(coll)

        # New instance forces reload from disk
        repo2 = FilesystemCollectionRepository(library_root)
        found = repo2.find_by_id(CollectionId("my-project"))

        assert found is not None
        assert found.name == "My Research Project"
        assert found.paper_count == 2
        refs = found.paper_refs
        ref_ids = {r.paper_id.value for r in refs}
        assert "10.1234/a" in ref_ids
        assert "sha256:abcdef1234567890" in ref_ids


# ============================================================
# find_all
# ============================================================


class TestFindAll:
    """Tests for find_all method."""

    def test_find_all_returns_multiple(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        repo.save(_make_collection("proj-a", "Project A"))
        repo.save(_make_collection("proj-b", "Project B"))

        result = repo.find_all()
        assert len(result) == 2
        names = {c.name for c in result}
        assert "Project A" in names
        assert "Project B" in names


# ============================================================
# delete
# ============================================================


class TestDelete:
    """Tests for delete method."""

    def test_delete_removes_yaml_file(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection()
        repo.save(coll)

        repo.delete(CollectionId("proj-alpha"))

        yaml_path = library_root / ".collections" / "proj-alpha.yaml"
        assert not yaml_path.exists()

    def test_delete_makes_unfindable(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection()
        repo.save(coll)
        repo.delete(CollectionId("proj-alpha"))

        assert repo.find_by_id(CollectionId("proj-alpha")) is None

    def test_delete_nonexistent_raises(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        with pytest.raises(KeyError):
            repo.delete(CollectionId("nonexistent"))


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_collection_no_papers(self, tmp_path: Path) -> None:
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection(paper_ids=[])
        repo.save(coll)

        found = repo.find_by_id(CollectionId("proj-alpha"))
        assert found is not None
        assert found.paper_count == 0

    def test_collection_id_with_special_chars(self, tmp_path: Path) -> None:
        """Collection IDs are sanitized for filesystem safety."""
        library_root = _setup_library(tmp_path)
        repo = FilesystemCollectionRepository(library_root)

        coll = _make_collection(coll_id="my project 2024", name="My Project")
        repo.save(coll)

        found = repo.find_by_id(CollectionId("my project 2024"))
        assert found is not None
