"""Tests for domain port interfaces.

Verifies that the abstract base classes are properly defined
and cannot be instantiated directly.
"""

from __future__ import annotations

import pytest

from src.domain.ports import (
    CollectionRepository,
    MetadataResolver,
    PaperRepository,
)


class TestPaperRepository:
    """Tests for PaperRepository abstract interface."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            PaperRepository()  # type: ignore[abstract]

    def test_has_required_methods(self) -> None:
        assert hasattr(PaperRepository, "find_by_id")
        assert hasattr(PaperRepository, "find_all")
        assert hasattr(PaperRepository, "save")
        assert hasattr(PaperRepository, "delete")


class TestCollectionRepository:
    """Tests for CollectionRepository abstract interface."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            CollectionRepository()  # type: ignore[abstract]

    def test_has_required_methods(self) -> None:
        assert hasattr(CollectionRepository, "find_by_id")
        assert hasattr(CollectionRepository, "find_all")
        assert hasattr(CollectionRepository, "save")
        assert hasattr(CollectionRepository, "delete")


class TestMetadataResolver:
    """Tests for MetadataResolver abstract interface."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            MetadataResolver()  # type: ignore[abstract]

    def test_has_required_methods(self) -> None:
        assert hasattr(MetadataResolver, "resolve")
