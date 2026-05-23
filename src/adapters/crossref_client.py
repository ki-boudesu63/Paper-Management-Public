"""CrossRef API client implementing MetadataResolver port.

Uses httpx (synchronous) to query CrossRef for bibliographic metadata.
Implements the Anti-Corruption Layer (ACL) pattern: CrossRef JSON -> domain Metadata.

Polite pool compliance: User-Agent includes contact email.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.domain.paper import DOI, Author, Metadata, PublicationYear
from src.domain.ports import MetadataResolver

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

CROSSREF_BASE_URL = "https://api.crossref.org"
TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
APP_NAME = "PaperManagement"
APP_VERSION = "0.1.0"


class CrossRefMetadataResolver(MetadataResolver):
    """Concrete MetadataResolver that queries the CrossRef REST API.

    Features:
    - Polite pool: User-Agent header includes contact email
    - Timeout: 10 seconds per request
    - Retry: up to 3 attempts on transient failures
    - ACL: maps CrossRef JSON to domain Metadata value objects
    """

    def __init__(self, contact_email: str) -> None:
        self._contact_email = contact_email
        self._user_agent = f"{APP_NAME}/{APP_VERSION} (mailto:{contact_email})"

    # ============================================================
    # Public API (Port implementation)
    # ============================================================

    def resolve(self, doi: DOI) -> Metadata | None:
        """Resolve metadata for a given DOI via CrossRef API.

        Returns None if resolution fails for any reason.
        """
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"
        headers = {"User-Agent": self._user_agent}

        response = self._fetch_with_retry(url, headers)
        if response is None:
            return None

        return self._parse_response(response, doi)

    # ============================================================
    # Private helpers
    # ============================================================

    def _fetch_with_retry(
        self, url: str, headers: dict[str, str]
    ) -> dict[str, Any] | None:
        """Fetch a URL with retry logic.

        Returns parsed JSON dict on success, None on failure.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                    resp = client.get(url, headers=headers)

                if resp.status_code == 200:
                    return resp.json()

                logger.warning(
                    "CrossRef returned status %d for %s (attempt %d/%d)",
                    resp.status_code,
                    url,
                    attempt,
                    MAX_RETRIES,
                )

                # 404 is definitive, no retry
                if resp.status_code == 404:
                    return None

            except httpx.TimeoutException:
                logger.warning(
                    "CrossRef request timed out for %s (attempt %d/%d)",
                    url,
                    attempt,
                    MAX_RETRIES,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "CrossRef request failed for %s: %s (attempt %d/%d)",
                    url,
                    exc,
                    attempt,
                    MAX_RETRIES,
                )
            except ValueError:
                logger.warning(
                    "CrossRef returned invalid JSON for %s (attempt %d/%d)",
                    url,
                    attempt,
                    MAX_RETRIES,
                )

        return None

    def _parse_response(self, data: dict[str, Any], doi: DOI) -> Metadata | None:
        """Parse CrossRef JSON response into domain Metadata.

        Returns None if required fields are missing or malformed.
        """
        try:
            message = data.get("message", {})

            title = self._extract_title(message)
            if not title:
                return None

            authors = self._extract_authors(message)
            if not authors:
                return None

            year = self._extract_year(message)
            if year is None:
                return None

            return Metadata(
                title=title,
                authors=tuple(authors),
                year=PublicationYear(year),
                doi=doi,
                journal=self._extract_first_text(message, "container-title"),
                journal_abbrev=self._extract_first_text(
                    message, "short-container-title"
                ),
                volume=self._extract_text(message, "volume"),
                issue=self._extract_text(message, "issue"),
                pages=self._extract_text(message, "page"),
            )
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse CrossRef response: %s", exc)
            return None

    @staticmethod
    def _extract_title(message: dict[str, Any]) -> str:
        """Extract the first title from the message."""
        titles = message.get("title", [])
        if not titles:
            return ""
        return titles[0]

    @staticmethod
    def _extract_first_text(message: dict[str, Any], key: str) -> str:
        """Extract the first string value from a list field."""
        values = message.get(key, [])
        if not isinstance(values, list) or not values:
            return ""
        return str(values[0])

    @staticmethod
    def _extract_text(message: dict[str, Any], key: str) -> str:
        """Extract a scalar value as a string."""
        value = message.get(key, "")
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _extract_authors(message: dict[str, Any]) -> list[Author]:
        """Extract authors from the message, mapping to domain Author."""
        raw_authors = message.get("author", [])
        authors: list[Author] = []
        for raw in raw_authors:
            family = raw.get("family", "")
            given = raw.get("given", "")
            if family:
                authors.append(Author(family_name=family, given_name=given))
        return authors

    @staticmethod
    def _extract_year(message: dict[str, Any]) -> int | None:
        """Extract publication year from the message.

        Priority: published-print > published-online > issued.
        """
        for key in ("published-print", "published-online", "issued"):
            date_info = message.get(key)
            if date_info and "date-parts" in date_info:
                date_parts = date_info["date-parts"]
                if date_parts and date_parts[0]:
                    return date_parts[0][0]
        return None
