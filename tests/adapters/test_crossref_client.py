"""Tests for CrossRefMetadataResolver.

All tests use respx to mock HTTP responses — no real network calls.
Covers happy path, error handling, retry logic, and ACL mapping.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.adapters.crossref_client import (
    CROSSREF_BASE_URL,
    CrossRefMetadataResolver,
)
from src.domain.paper import DOI

# ============================================================
# Sample CrossRef API Responses
# ============================================================

SAMPLE_CROSSREF_RESPONSE = {
    "status": "ok",
    "message": {
        "title": ["Mechanical Stress in Tracheal Regeneration"],
        "author": [
            {"family": "Kitano", "given": "Takahiro"},
            {"family": "Smith", "given": "John"},
        ],
        "published-print": {"date-parts": [[2024]]},
        "DOI": "10.1234/test.5678",
    },
}

SAMPLE_SINGLE_AUTHOR_RESPONSE = {
    "status": "ok",
    "message": {
        "title": ["Solo Author Paper"],
        "author": [{"family": "Anderson", "given": "Marie"}],
        "published-online": {"date-parts": [[2023]]},
        "DOI": "10.5678/solo.001",
    },
}

SAMPLE_NO_PRINT_DATE_RESPONSE = {
    "status": "ok",
    "message": {
        "title": ["Online Only Paper"],
        "author": [{"family": "Chen", "given": "Wei"}],
        "published-online": {"date-parts": [[2025]]},
        "DOI": "10.9999/online.001",
    },
}

SAMPLE_MINIMAL_RESPONSE = {
    "status": "ok",
    "message": {
        "title": ["Minimal Paper"],
        "author": [{"family": "Unknown"}],
        "issued": {"date-parts": [[2020]]},
        "DOI": "10.0000/minimal",
    },
}

SAMPLE_BIBLIOGRAPHIC_RESPONSE = {
    "status": "ok",
    "message": {
        "title": ["Bibliographic Paper"],
        "author": [{"family": "Okita", "given": "K"}],
        "published-print": {"date-parts": [[2011]]},
        "DOI": "10.1234/biblio.001",
        "container-title": ["Stem Cell Reports"],
        "short-container-title": ["Stem Cell Rep"],
        "volume": "12",
        "issue": "3",
        "page": "2364-2370",
    },
}


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def resolver() -> CrossRefMetadataResolver:
    """Create a resolver with a test email."""
    return CrossRefMetadataResolver(contact_email="test@example.com")


# ============================================================
# Happy Path
# ============================================================


class TestResolveHappyPath:
    """Tests for successful metadata resolution."""

    @respx.mock
    def test_resolve_returns_metadata(self, resolver: CrossRefMetadataResolver) -> None:
        doi = DOI("10.1234/test.5678")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(
            return_value=httpx.Response(200, json=SAMPLE_CROSSREF_RESPONSE)
        )

        result = resolver.resolve(doi)

        assert result is not None
        assert result.title == "Mechanical Stress in Tracheal Regeneration"
        assert len(result.authors) == 2
        assert result.authors[0].family_name == "Kitano"
        assert result.authors[0].given_name == "Takahiro"
        assert result.authors[1].family_name == "Smith"
        assert result.year.value == 2024
        assert result.doi is not None
        assert result.doi.value == "10.1234/test.5678"
        assert result.abstract == ""

    @respx.mock
    def test_resolve_maps_bibliographic_fields(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.1234/biblio.001")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(
            return_value=httpx.Response(200, json=SAMPLE_BIBLIOGRAPHIC_RESPONSE)
        )

        result = resolver.resolve(doi)

        assert result is not None
        assert result.journal == "Stem Cell Reports"
        assert result.journal_abbrev == "Stem Cell Rep"
        assert result.volume == "12"
        assert result.issue == "3"
        assert result.pages == "2364-2370"

    @respx.mock
    def test_resolve_single_author(self, resolver: CrossRefMetadataResolver) -> None:
        doi = DOI("10.5678/solo.001")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(
            return_value=httpx.Response(200, json=SAMPLE_SINGLE_AUTHOR_RESPONSE)
        )

        result = resolver.resolve(doi)

        assert result is not None
        assert len(result.authors) == 1
        assert result.authors[0].family_name == "Anderson"

    @respx.mock
    def test_resolve_uses_published_online_date(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.9999/online.001")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(
            return_value=httpx.Response(200, json=SAMPLE_NO_PRINT_DATE_RESPONSE)
        )

        result = resolver.resolve(doi)

        assert result is not None
        assert result.year.value == 2025

    @respx.mock
    def test_resolve_minimal_author_no_given_name(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.0000/minimal")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(
            return_value=httpx.Response(200, json=SAMPLE_MINIMAL_RESPONSE)
        )

        result = resolver.resolve(doi)

        assert result is not None
        assert result.authors[0].family_name == "Unknown"
        assert result.authors[0].given_name == ""


# ============================================================
# Error Cases
# ============================================================


class TestResolveErrors:
    """Tests for error handling."""

    @respx.mock
    def test_resolve_404_returns_none(self, resolver: CrossRefMetadataResolver) -> None:
        doi = DOI("10.1234/nonexistent")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(return_value=httpx.Response(404))

        result = resolver.resolve(doi)
        assert result is None

    @respx.mock
    def test_resolve_500_returns_none(self, resolver: CrossRefMetadataResolver) -> None:
        doi = DOI("10.1234/server.error")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(return_value=httpx.Response(500))

        result = resolver.resolve(doi)
        assert result is None

    @respx.mock
    def test_resolve_timeout_returns_none(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.1234/timeout")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(side_effect=httpx.TimeoutException("timeout"))

        result = resolver.resolve(doi)
        assert result is None

    @respx.mock
    def test_resolve_network_error_returns_none(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.1234/network.fail")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(side_effect=httpx.ConnectError("connection failed"))

        result = resolver.resolve(doi)
        assert result is None

    @respx.mock
    def test_resolve_invalid_json_returns_none(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.1234/bad.json")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        respx.get(url).mock(return_value=httpx.Response(200, text="not json"))

        result = resolver.resolve(doi)
        assert result is None

    @respx.mock
    def test_resolve_missing_title_returns_none(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.1234/no.title")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        response_data = {
            "status": "ok",
            "message": {
                "title": [],
                "author": [{"family": "Test"}],
                "issued": {"date-parts": [[2024]]},
            },
        }
        respx.get(url).mock(return_value=httpx.Response(200, json=response_data))

        result = resolver.resolve(doi)
        assert result is None


# ============================================================
# Polite Pool / User-Agent
# ============================================================


class TestPolitePool:
    """Tests for CrossRef polite pool compliance."""

    @respx.mock
    def test_user_agent_contains_email(
        self, resolver: CrossRefMetadataResolver
    ) -> None:
        doi = DOI("10.1234/test.5678")
        url = f"{CROSSREF_BASE_URL}/works/{doi.value}"

        route = respx.get(url).mock(
            return_value=httpx.Response(200, json=SAMPLE_CROSSREF_RESPONSE)
        )

        resolver.resolve(doi)

        assert route.called
        request = route.calls[0].request
        user_agent = request.headers.get("user-agent", "")
        assert "test@example.com" in user_agent
