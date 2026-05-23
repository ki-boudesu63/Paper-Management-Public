"""CollectionAppService: CRUD operations for paper collections.

Collections are groups of paper references (PaperRef) tied to
writing projects. Papers are never moved; only ID references are stored.
"""

from __future__ import annotations

import logging
import uuid

from src.domain.collection import Collection, CollectionId, PaperRef
from src.domain.paper import Paper, PaperId
from src.domain.ports import CollectionRepository, PaperRepository

logger = logging.getLogger(__name__)


# ============================================================
# CollectionAppService
# ============================================================


class CollectionAppService:
    """Application service for collection CRUD operations.

    Validates that papers exist before adding them to collections.
    """

    def __init__(
        self,
        collection_repo: CollectionRepository,
        paper_repo: PaperRepository,
    ) -> None:
        self._collection_repo = collection_repo
        self._paper_repo = paper_repo

    # ============================================================
    # Public API
    # ============================================================

    def create_collection(self, name: str) -> Collection:
        """Create a new collection with the given name.

        Generates a UUID-based CollectionId.

        Args:
            name: Display name for the collection.

        Returns:
            The newly created Collection.

        Raises:
            ValueError: If name is empty.
        """
        if not name.strip():
            raise ValueError("Collection name must not be empty")

        collection_id = CollectionId(str(uuid.uuid4()))
        collection = Collection(id=collection_id, name=name)
        self._collection_repo.save(collection)

        logger.info("Created collection: %s (%s)", name, collection_id.value)
        return collection

    def list_collections(self) -> list[Collection]:
        """Return all collections, sorted by name."""
        collections = self._collection_repo.find_all()
        return sorted(collections, key=lambda c: c.name.lower())

    def get_collection(self, collection_id: str) -> Collection | None:
        """Get a single collection by its ID string.

        Returns None if not found.
        """
        cid = CollectionId(collection_id)
        return self._collection_repo.find_by_id(cid)

    def list_papers_in_collection(self, collection_id: str) -> list[Paper]:
        """Return papers referenced by a collection.

        Missing paper references are skipped so stale collection YAML does not
        break the UI.

        Raises:
            KeyError: If collection not found.
        """
        collection = self._get_collection_or_raise(collection_id)
        papers: list[Paper] = []
        for ref in collection.paper_refs:
            paper = self._paper_repo.find_by_id(ref.paper_id)
            if paper is not None:
                papers.append(paper)
        return papers

    def list_collection_names_for_paper(self, paper_id: str) -> list[str]:
        """Return names of collections that contain the given paper."""
        ref = PaperRef(paper_id=PaperId(paper_id))
        names = [
            collection.name
            for collection in self._collection_repo.find_all()
            if collection.contains(ref)
        ]
        return sorted(names, key=str.lower)

    def add_paper_to_collection(self, collection_id: str, paper_id: str) -> Collection:
        """Add a paper reference to a collection.

        Validates that both the collection and paper exist.

        Args:
            collection_id: The collection's ID string.
            paper_id: The paper's ID string.

        Returns:
            The updated Collection.

        Raises:
            KeyError: If collection or paper not found.
        """
        collection = self._get_collection_or_raise(collection_id)
        paper = self._paper_repo.find_by_id(PaperId(paper_id))
        if paper is None:
            raise KeyError(f"Paper not found: {paper_id}")

        ref = PaperRef(paper_id=paper.id)
        collection.add_paper(ref)
        self._collection_repo.save(collection)

        logger.info(
            "Added paper %s to collection %s",
            paper_id,
            collection_id,
        )
        return collection

    def remove_paper_from_collection(
        self, collection_id: str, paper_id: str
    ) -> Collection:
        """Remove a paper reference from a collection.

        Args:
            collection_id: The collection's ID string.
            paper_id: The paper's ID string.

        Returns:
            The updated Collection.

        Raises:
            KeyError: If collection not found.
            ValueError: If paper reference not in collection.
        """
        collection = self._get_collection_or_raise(collection_id)
        ref = PaperRef(paper_id=PaperId(paper_id))
        collection.remove_paper(ref)
        self._collection_repo.save(collection)

        logger.info(
            "Removed paper %s from collection %s",
            paper_id,
            collection_id,
        )
        return collection

    def remove_paper_from_all_collections(self, paper_id: str) -> int:
        """Remove a paper reference from every collection that contains it.

        Iterates all collections and silently removes the PaperRef if present.
        Collections that do not reference the paper are left unchanged.

        Args:
            paper_id: The paper's ID string.

        Returns:
            Number of collections that were modified.
        """
        pid = PaperId(paper_id)
        ref = PaperRef(paper_id=pid)
        modified_count = 0

        for collection in self._collection_repo.find_all():
            if collection.contains(ref):
                collection.remove_paper(ref)
                self._collection_repo.save(collection)
                modified_count += 1
                logger.info(
                    "Removed paper %s from collection %s",
                    paper_id,
                    collection.id.value,
                )

        return modified_count

    def delete_collection(self, collection_id: str) -> None:
        """Delete a collection.

        Args:
            collection_id: The collection's ID string.

        Raises:
            KeyError: If collection not found.
        """
        cid = CollectionId(collection_id)
        existing = self._collection_repo.find_by_id(cid)
        if existing is None:
            raise KeyError(f"Collection not found: {collection_id}")

        self._collection_repo.delete(cid)
        logger.info("Deleted collection: %s", collection_id)

    # ============================================================
    # Private helpers
    # ============================================================

    def _get_collection_or_raise(self, collection_id: str) -> Collection:
        """Retrieve a collection or raise KeyError."""
        cid = CollectionId(collection_id)
        collection = self._collection_repo.find_by_id(cid)
        if collection is None:
            raise KeyError(f"Collection not found: {collection_id}")
        return collection
