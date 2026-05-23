"""Domain port interfaces (Abstract Base Classes).

Defines the contracts that adapters must implement.
Domain layer depends only on these abstractions, never on concrete implementations.

Pure Python, no external library dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.collection import Collection, CollectionId
from src.domain.paper import DOI, Metadata, Paper, PaperId

# ============================================================
# PaperRepository Port
# ============================================================


class PaperRepository(ABC):
    """Abstract repository for Paper aggregate persistence.

    Concrete implementations handle filesystem operations
    (initial-letter folder traversal, PDF/MD pair management).
    """

    @abstractmethod
    def find_by_id(self, paper_id: PaperId) -> Paper | None:
        """Find a paper by its ID.

        Returns None if not found.
        """

    @abstractmethod
    def find_all(self) -> list[Paper]:
        """Return all papers in the library."""

    @abstractmethod
    def save(self, paper: Paper) -> None:
        """Persist a paper (create or update).

        Handles PDF placement and MD note generation.
        """

    def attach_pdf(self, paper_id: PaperId, pdf_path: str) -> Paper:
        """Attach a PDF to an existing paper and return the updated paper."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, paper_id: PaperId) -> None:
        """Remove a paper and its associated files."""


# ============================================================
# CollectionRepository Port
# ============================================================


class CollectionRepository(ABC):
    """Abstract repository for Collection aggregate persistence.

    Concrete implementations store one YAML file per collection
    under <library_root>/.collections/.
    """

    @abstractmethod
    def find_by_id(self, collection_id: CollectionId) -> Collection | None:
        """Find a collection by its ID.

        Returns None if not found.
        """

    @abstractmethod
    def find_all(self) -> list[Collection]:
        """Return all collections."""

    @abstractmethod
    def save(self, collection: Collection) -> None:
        """Persist a collection (create or update)."""

    @abstractmethod
    def delete(self, collection_id: CollectionId) -> None:
        """Remove a collection definition."""


# ============================================================
# MetadataResolver Port
# ============================================================


class MetadataResolver(ABC):
    """Abstract service for resolving paper metadata from a DOI.

    Concrete implementation calls CrossRef API (ACL pattern).
    """

    @abstractmethod
    def resolve(self, doi: DOI) -> Metadata | None:
        """Resolve metadata for a given DOI.

        Returns None if resolution fails (not found, timeout, etc.).
        """
