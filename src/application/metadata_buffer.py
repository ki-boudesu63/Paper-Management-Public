"""In-memory metadata buffer for Chrome extension integration.

Stores metadata POSTed by the Chrome extension, keyed by DOI or title.
Entries expire after a configurable TTL (default 10 minutes).
On PDF detection, the ImportAppService queries this buffer with
author/year fuzzy matching to find pre-fetched metadata.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from src.domain.paper import Metadata

# ============================================================
# Constants
# ============================================================

DEFAULT_TTL_SECONDS = 600  # 10 minutes
FUZZY_MATCH_THRESHOLD = 0.8  # Not used yet; reserved for future scoring


# ============================================================
# Buffer Entry
# ============================================================


@dataclass
class BufferEntry:
    """A single buffered metadata entry with expiration timestamp."""

    metadata: Metadata
    expires_at: float


# ============================================================
# MetadataBuffer
# ============================================================


class MetadataBuffer:
    """Thread-safe in-memory buffer for Chrome extension metadata.

    Keys are DOI strings (normalized) or titles (lowercased).
    Expired entries are lazily purged on access.
    """

    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._by_doi: dict[str, BufferEntry] = {}
        self._by_title: dict[str, BufferEntry] = {}
        self._lock = threading.Lock()

    @property
    def ttl_seconds(self) -> float:
        """Return the configured TTL in seconds."""
        return self._ttl_seconds

    def put(self, metadata: Metadata) -> None:
        """Store metadata, keyed by DOI (if present) and title."""
        now = time.time()
        entry = BufferEntry(
            metadata=metadata,
            expires_at=now + self._ttl_seconds,
        )

        with self._lock:
            if metadata.doi is not None:
                self._by_doi[metadata.doi.value] = entry
            title_key = metadata.title.strip().lower()
            if title_key:
                self._by_title[title_key] = entry

    def lookup_by_doi(self, doi_value: str) -> Metadata | None:
        """Look up metadata by normalized DOI string.

        Returns None if not found or expired.
        """
        now = time.time()
        with self._lock:
            entry = self._by_doi.get(doi_value)
            if entry is None:
                return None
            if entry.expires_at < now:
                del self._by_doi[doi_value]
                return None
            return entry.metadata

    def lookup_by_title(self, title: str) -> Metadata | None:
        """Look up metadata by exact title match (case-insensitive).

        Returns None if not found or expired.
        """
        now = time.time()
        key = title.strip().lower()
        with self._lock:
            entry = self._by_title.get(key)
            if entry is None:
                return None
            if entry.expires_at < now:
                del self._by_title[key]
                return None
            return entry.metadata

    def lookup_by_author_year(self, family_name: str, year: int) -> Metadata | None:
        """Fuzzy match: find metadata where first author family name
        and year match any buffered entry.

        This is used when a PDF is detected but no DOI is available.
        Matching is case-insensitive on author family name.
        """
        now = time.time()
        target_name = family_name.strip().lower()

        with self._lock:
            # Search DOI-keyed entries first, then title-keyed
            for store in (self._by_doi, self._by_title):
                expired_keys: list[str] = []
                for key, entry in store.items():
                    if entry.expires_at < now:
                        expired_keys.append(key)
                        continue
                    meta = entry.metadata
                    if (
                        meta.year.value == year
                        and meta.first_author.family_name.strip().lower() == target_name
                    ):
                        return meta
                # Lazy purge expired
                for k in expired_keys:
                    del store[k]

        return None

    def remove_by_doi(self, doi_value: str) -> None:
        """Remove an entry by DOI (after successful import)."""
        with self._lock:
            self._by_doi.pop(doi_value, None)

    def remove_by_title(self, title: str) -> None:
        """Remove an entry by title (after successful import)."""
        key = title.strip().lower()
        with self._lock:
            self._by_title.pop(key, None)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._by_doi.clear()
            self._by_title.clear()

    def size(self) -> int:
        """Return total number of entries (DOI-keyed + title-keyed, may overlap)."""
        with self._lock:
            return len(self._by_doi) + len(self._by_title)
