"""LibraryAppService: paper listing, search, and detail retrieval.

Provides lightweight metadata search (author/year/tag/title) over the
in-memory cache maintained by PaperRepository. Full-text search is
delegated to Obsidian via obsidian:// URI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.domain.paper import Paper, PaperId
from src.domain.ports import PaperRepository

logger = logging.getLogger(__name__)


# ============================================================
# Search Query
# ============================================================


@dataclass(frozen=True)
class SearchQuery:
    """Lightweight metadata search criteria.

    All fields are optional. When multiple fields are set,
    they are combined with AND logic.
    """

    author: str = ""
    year: int | None = None
    tag: str = ""
    title: str = ""


# ============================================================
# LibraryAppService
# ============================================================


class LibraryAppService:
    """Application service for browsing and searching the paper library.

    Depends on PaperRepository for data access. The repository must have
    been scanned (scan()) before this service is used.
    """

    def __init__(self, paper_repo: PaperRepository) -> None:
        self._paper_repo = paper_repo

    def initialize(self) -> None:
        """Initialize the service: scan repository to build cache."""
        self._paper_repo.scan()

    # ============================================================
    # Public API
    # ============================================================

    def list_all(self) -> list[Paper]:
        """Return all papers in the library, sorted by first author family name."""
        papers = self._paper_repo.find_all()
        return sorted(
            papers,
            key=lambda p: p.metadata.first_author.family_name.lower(),
        )

    def get_by_id(self, paper_id: PaperId) -> Paper | None:
        """Get a single paper by its ID.

        Returns None if not found.
        """
        return self._paper_repo.find_by_id(paper_id)

    def search(self, query: SearchQuery) -> list[Paper]:
        """Search papers by lightweight metadata criteria.

        Filters are combined with AND logic. Empty/None fields are skipped.
        String matching is case-insensitive substring match.

        Args:
            query: Search criteria.

        Returns:
            List of matching papers, sorted by first author family name.
        """
        papers = self._paper_repo.find_all()
        results = [p for p in papers if self._matches(p, query)]
        return sorted(
            results,
            key=lambda p: p.metadata.first_author.family_name.lower(),
        )

    def fulltext_search(self, query_text: str) -> list[Paper]:
        """Cross-field free-text AND search over all papers.

        Splits *query_text* on whitespace into terms. A paper matches
        only when **every** term is found (case-insensitive substring)
        in at least one of its searchable fields:

        - author family / given names (all authors)
        - title
        - abstract
        - memo
        - year (stringified)
        - tags

        An empty / whitespace-only *query_text* returns all papers.

        Returns:
            Matching papers sorted by first author family name.
        """
        terms = query_text.split()
        if not terms:
            return self.list_all()

        lower_terms = [t.lower() for t in terms]
        papers = self._paper_repo.find_all()
        results = [p for p in papers if self._matches_all_terms(p, lower_terms)]
        return sorted(
            results,
            key=lambda p: p.metadata.first_author.family_name.lower(),
        )

    def delete_paper(self, paper_id: PaperId) -> bool:
        """Delete a paper from the repository (files + cache).

        Returns True if the paper was found and deleted, False if not found.
        Caller is responsible for also removing collection references
        (cross-aggregate coordination belongs in the web/orchestration layer
        or a dedicated application service).
        """
        paper = self._paper_repo.find_by_id(paper_id)
        if paper is None:
            return False
        self._paper_repo.delete(paper_id)
        logger.info("Deleted paper: %s", paper_id.value)
        return True

    def rescan(self) -> int:
        """Re-scan the library root and rebuild the in-memory cache.

        Returns the number of papers found after the scan.
        """
        self._paper_repo.scan()
        count = len(self._paper_repo.find_all())
        logger.info("Rescan complete: %d papers found", count)
        return count

    def list_by_initial(self, letter: str) -> list[Paper]:
        """Return all papers whose initial letter matches.

        Args:
            letter: A single uppercase letter (A-Z) or '#'.

        Returns:
            Matching papers sorted by first author family name.
        """
        target = letter.upper()
        papers = self._paper_repo.find_all()
        filtered = [p for p in papers if p.initial_letter.letter == target]
        return sorted(
            filtered,
            key=lambda p: p.metadata.first_author.family_name.lower(),
        )

    # ============================================================
    # Private helpers
    # ============================================================

    @staticmethod
    def _term_matches_paper(paper: Paper, term: str) -> bool:
        """Check if a single lowercase term matches any searchable field."""
        # Author names
        for author in paper.metadata.authors:
            if term in author.family_name.lower():
                return True
            if term in author.given_name.lower():
                return True

        # Title
        if term in paper.metadata.title.lower():
            return True

        # Abstract (may be empty string)
        if paper.metadata.abstract and term in paper.metadata.abstract.lower():
            return True

        # Memo (may be empty string)
        if paper.metadata.memo and term in paper.metadata.memo.lower():
            return True

        # Year (stringified)
        if term in str(paper.metadata.year.value):
            return True

        # Tags
        for tag in paper.tags:
            if term in tag.lower():
                return True

        return False

    @staticmethod
    def _matches_all_terms(paper: Paper, lower_terms: list[str]) -> bool:
        """Check if a paper matches ALL terms (AND logic)."""
        return all(
            LibraryAppService._term_matches_paper(paper, term) for term in lower_terms
        )

    @staticmethod
    def _matches(paper: Paper, query: SearchQuery) -> bool:
        """Check if a paper matches all non-empty search criteria."""
        if query.author:
            author_match = any(
                query.author.lower() in a.family_name.lower()
                or query.author.lower() in a.given_name.lower()
                for a in paper.metadata.authors
            )
            if not author_match:
                return False

        if query.year is not None:
            if paper.metadata.year.value != query.year:
                return False

        if query.tag:
            tag_match = any(query.tag.lower() in t.lower() for t in paper.tags)
            if not tag_match:
                return False

        if query.title:
            if query.title.lower() not in paper.metadata.title.lower():
                return False

        return True
