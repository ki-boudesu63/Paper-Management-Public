"""Domain model for Collection aggregate.

Contains CollectionId, PaperRef (Value Objects) and Collection (Entity).

Pure Python, no external library dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.paper import PaperId

# ============================================================
# CollectionId
# ============================================================


@dataclass(frozen=True, eq=True)
class CollectionId:
    """Unique identifier for a collection."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Collection id must not be empty")

    def __hash__(self) -> int:
        return hash(self.value)


# ============================================================
# PaperRef Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class PaperRef:
    """Reference to a paper by its PaperId.

    Does not hold the paper entity itself — only an ID reference.
    """

    paper_id: PaperId

    def __hash__(self) -> int:
        return hash(self.paper_id)


# ============================================================
# Collection Entity (Aggregate Root)
# ============================================================


@dataclass(eq=False)
class Collection:
    """Collection entity representing a project-specific group of paper references.

    Papers are referenced, not moved. A single paper can belong to
    multiple collections simultaneously.
    """

    id: CollectionId
    name: str
    _paper_refs: list[PaperRef] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Collection name must not be empty")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Collection):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def paper_refs(self) -> list[PaperRef]:
        """Return a copy of the paper references list."""
        return list(self._paper_refs)

    @property
    def paper_count(self) -> int:
        """Return the number of papers in this collection."""
        return len(self._paper_refs)

    def add_paper(self, ref: PaperRef) -> None:
        """Add a paper reference to the collection.

        Duplicates are silently ignored (idempotent operation).
        """
        if self.contains(ref):
            return
        self._paper_refs.append(ref)

    def remove_paper(self, ref: PaperRef) -> None:
        """Remove a paper reference from the collection.

        Raises:
            ValueError: If the paper reference is not in the collection.
        """
        if not self.contains(ref):
            raise ValueError(
                f"PaperRef {ref.paper_id.value} not found in collection"
            )
        self._paper_refs = [r for r in self._paper_refs if r != ref]

    def contains(self, ref: PaperRef) -> bool:
        """Check if a paper reference exists in this collection."""
        return ref in self._paper_refs
