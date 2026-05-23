"""Tests for POST /api/import/metadata endpoint.

Verifies:
- Successful metadata reception and buffering
- Invalid payload rejection (missing fields, bad types)
- CORS headers for localhost origins
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.application.import_service import ImportResult
from tests.web.conftest import make_paper

# ============================================================
# Valid payload fixture
# ============================================================


@pytest.fixture()
def valid_payload() -> dict:
    """A complete valid metadata payload from the Chrome extension."""
    return {
        "title": "Tracheal Regeneration Under Mechanical Stress",
        "doi": "10.1234/test.5678",
        "year": 2024,
        "first_author": "Kitano",
        "author_count": 3,
        "authors": [
            {"family": "Kitano", "given": "Takahiro"},
            {"family": "Mizuno", "given": "Yuki"},
            {"family": "Tanaka", "given": "Hiroshi"},
        ],
        "source": "citation_meta",
    }


# ============================================================
# Happy path tests
# ============================================================


class TestReceiveMetadataSuccess:
    """Test successful metadata reception."""

    def test_valid_full_payload(self, client: TestClient, valid_payload: dict) -> None:
        """Full payload with DOI, year, structured authors should succeed."""
        resp = client.post("/api/import/metadata", json=valid_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "Tracheal Regeneration" in data["message"]

    def test_valid_minimal_payload(self, client: TestClient) -> None:
        """Minimal payload with title, first_author, year should succeed."""
        payload = {
            "title": "Minimal Test Paper",
            "doi": None,
            "year": 2023,
            "first_author": "Smith",
            "author_count": 1,
            "authors": [],
            "source": "doi_scan",
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_valid_without_doi(self, client: TestClient) -> None:
        """Payload without DOI should still succeed."""
        payload = {
            "title": "No DOI Paper",
            "year": 2025,
            "first_author": "Anderson",
            "author_count": 1,
            "authors": [{"family": "Anderson", "given": "James"}],
            "source": "citation_meta",
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_receive_calls_import_service(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
        valid_payload: dict,
    ) -> None:
        """Endpoint should call receive_extension_metadata on the import service."""
        resp = client.post("/api/import/metadata", json=valid_payload)
        assert resp.status_code == 200
        mock_import_service.receive_extension_metadata.assert_called_once()

    def test_doi_payload_registers_md_only_paper(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
        valid_payload: dict,
    ) -> None:
        """Payloads with DOI should register a metadata-only paper immediately."""
        resp = client.post("/api/import/metadata", json=valid_payload)

        assert resp.status_code == 200
        mock_import_service.register_metadata_only.assert_called_once()

    def test_payload_without_doi_only_buffers_metadata(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Payloads without DOI are buffered for later PDF import only."""
        payload = {
            "title": "No DOI Paper",
            "doi": None,
            "year": 2024,
            "first_author": "Smith",
            "author_count": 1,
            "authors": [],
            "source": "citation_meta",
        }

        resp = client.post("/api/import/metadata", json=payload)

        assert resp.status_code == 200
        mock_import_service.receive_extension_metadata.assert_called_once()
        mock_import_service.register_metadata_only.assert_not_called()

    def test_buffered_metadata_has_correct_doi(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
        valid_payload: dict,
    ) -> None:
        """Buffered Metadata should contain the DOI from the payload."""
        client.post("/api/import/metadata", json=valid_payload)
        call_args = mock_import_service.receive_extension_metadata.call_args
        metadata = call_args[0][0]
        assert metadata.doi is not None
        assert metadata.doi.value == "10.1234/test.5678"

    def test_buffered_metadata_has_correct_authors(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
        valid_payload: dict,
    ) -> None:
        """Buffered Metadata should contain all authors from the payload."""
        client.post("/api/import/metadata", json=valid_payload)
        call_args = mock_import_service.receive_extension_metadata.call_args
        metadata = call_args[0][0]
        assert len(metadata.authors) == 3
        assert metadata.first_author.family_name == "Kitano"

    def test_invalid_doi_still_accepted(self, client: TestClient) -> None:
        """Invalid DOI string should not reject the payload; DOI is set to None."""
        payload = {
            "title": "Paper With Bad DOI",
            "doi": "not-a-valid-doi",
            "year": 2024,
            "first_author": "Yamada",
            "author_count": 1,
            "authors": [{"family": "Yamada", "given": "Taro"}],
            "source": "citation_meta",
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 200


class TestImportDoi:
    """Test POST /api/import/doi batch imports."""

    def test_successful_registration(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Successful ImportResult should map to registered."""
        paper = make_paper(
            paper_id="10.1234/abc",
            title="Resolved DOI Paper",
            doi_value="10.1234/abc",
        )
        mock_import_service.register_metadata_only.return_value = ImportResult(
            pdf_path="",
            status="success",
            paper=paper,
        )

        resp = client.post("/api/import/doi", json={"dois": ["10.1234/abc"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == {"registered": 1, "duplicate": 0, "failed": 0}
        assert data["results"] == [
            {
                "doi": "10.1234/abc",
                "status": "registered",
                "title": "Resolved DOI Paper",
                "paper_id": "10.1234/abc",
            }
        ]
        mock_import_service.register_metadata_only.assert_called_once()
        call_kwargs = mock_import_service.register_metadata_only.call_args.kwargs
        assert call_kwargs["require_resolved"] is True

    def test_duplicate(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Duplicate ImportResult should map to duplicate."""
        paper = make_paper(
            paper_id="10.1234/dup",
            title="Existing DOI Paper",
            doi_value="10.1234/dup",
        )
        mock_import_service.register_metadata_only.return_value = ImportResult(
            pdf_path="",
            status="duplicate",
            paper=paper,
            message="Paper already exists: 10.1234/dup",
        )

        resp = client.post("/api/import/doi", json={"dois": ["10.1234/dup"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == {"registered": 0, "duplicate": 1, "failed": 0}
        assert data["results"][0]["status"] == "duplicate"
        assert data["results"][0]["title"] == "Existing DOI Paper"
        assert data["results"][0]["paper_id"] == "10.1234/dup"

    def test_invalid_doi_format(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Invalid DOI format should fail that item without calling the service."""
        resp = client.post("/api/import/doi", json={"dois": ["not-a-doi"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == {"registered": 0, "duplicate": 0, "failed": 1}
        assert data["results"][0]["doi"] == "not-a-doi"
        assert data["results"][0]["status"] == "failed"
        assert "DOI format invalid" in data["results"][0]["error"]
        mock_import_service.register_metadata_only.assert_not_called()

    def test_crossref_resolution_failure(
        self,
        client: TestClient,
        mock_import_service: MagicMock,
    ) -> None:
        """Unresolved CrossRef metadata should map to failed."""
        mock_import_service.register_metadata_only.return_value = ImportResult(
            pdf_path="",
            status="unsorted",
            message="Metadata resolution failed for DOI: 10.1234/missing",
        )

        resp = client.post("/api/import/doi", json={"dois": ["10.1234/missing"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == {"registered": 0, "duplicate": 0, "failed": 1}
        assert data["results"] == [
            {
                "doi": "10.1234/missing",
                "status": "failed",
                "error": "Metadata resolution failed for DOI: 10.1234/missing",
            }
        ]


# ============================================================
# Validation error tests
# ============================================================


class TestReceiveMetadataValidation:
    """Test payload validation and error responses."""

    def test_missing_title(self, client: TestClient) -> None:
        """Missing title should return 422."""
        payload = {
            "year": 2024,
            "first_author": "Kitano",
            "author_count": 1,
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 422

    def test_empty_title(self, client: TestClient) -> None:
        """Empty title string should return 422."""
        payload = {
            "title": "",
            "year": 2024,
            "first_author": "Kitano",
            "author_count": 1,
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 422

    def test_missing_authors_and_first_author(self, client: TestClient) -> None:
        """No authors at all should return 422."""
        payload = {
            "title": "Paper Without Authors",
            "year": 2024,
            "first_author": None,
            "author_count": 0,
            "authors": [],
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 422

    def test_missing_year(self, client: TestClient) -> None:
        """Missing year should return 422."""
        payload = {
            "title": "Paper Without Year",
            "year": None,
            "first_author": "Kitano",
            "author_count": 1,
            "authors": [{"family": "Kitano", "given": "Takahiro"}],
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 422

    def test_invalid_year_too_old(self, client: TestClient) -> None:
        """Year before 1900 should return 422."""
        payload = {
            "title": "Ancient Paper",
            "year": 1800,
            "first_author": "Ptolemy",
            "author_count": 1,
            "authors": [{"family": "Ptolemy", "given": ""}],
        }
        resp = client.post("/api/import/metadata", json=payload)
        assert resp.status_code == 422

    def test_empty_body(self, client: TestClient) -> None:
        """Empty JSON body should return 422."""
        resp = client.post("/api/import/metadata", json={})
        assert resp.status_code == 422

    def test_non_json_body(self, client: TestClient) -> None:
        """Non-JSON body should return 422."""
        resp = client.post(
            "/api/import/metadata",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ============================================================
# CORS tests
# ============================================================


class TestCORSHeaders:
    """Test CORS headers for Chrome extension requests."""

    def test_cors_allows_localhost_origin(
        self, client: TestClient, valid_payload: dict
    ) -> None:
        """Requests from http://127.0.0.1 should include CORS headers."""
        resp = client.post(
            "/api/import/metadata",
            json=valid_payload,
            headers={"Origin": "http://127.0.0.1"},
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_allows_localhost_name(
        self, client: TestClient, valid_payload: dict
    ) -> None:
        """Requests from http://localhost should include CORS headers."""
        resp = client.post(
            "/api/import/metadata",
            json=valid_payload,
            headers={"Origin": "http://localhost"},
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_preflight_options(self, client: TestClient) -> None:
        """OPTIONS preflight request should return 200 with CORS headers."""
        resp = client.options(
            "/api/import/metadata",
            headers={
                "Origin": "http://127.0.0.1",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


# ============================================================
# CORS regression: chrome-extension:// origin (Modification D)
# ============================================================


class TestCORSChromeExtensionRegression:
    """Regression tests for chrome-extension:// CORS support.

    The app uses allow_origin_regex=r"chrome-extension://.*" to match
    Chrome extension origins. These tests ensure this does not regress.
    """

    def test_chrome_extension_preflight_succeeds(self, client: TestClient) -> None:
        """OPTIONS preflight from chrome-extension:// origin must return 200."""
        ext_origin = "chrome-extension://abcdefghijklmnopqrstuvwxyz123456"
        resp = client.options(
            "/api/import/metadata",
            headers={
                "Origin": ext_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers
        assert resp.headers["access-control-allow-origin"] == ext_origin

    def test_chrome_extension_post_has_cors_headers(
        self, client: TestClient, valid_payload: dict
    ) -> None:
        """POST from chrome-extension:// origin should include CORS headers."""
        ext_origin = "chrome-extension://abcdefghijklmnopqrstuvwxyz123456"
        resp = client.post(
            "/api/import/metadata",
            json=valid_payload,
            headers={"Origin": ext_origin},
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers
        assert resp.headers["access-control-allow-origin"] == ext_origin

    def test_chrome_extension_different_id_also_works(
        self, client: TestClient, valid_payload: dict
    ) -> None:
        """Different extension IDs should all be matched by the regex."""
        ext_origin = "chrome-extension://zyxwvutsrqponmlkjihgfedcba987654"
        resp = client.post(
            "/api/import/metadata",
            json=valid_payload,
            headers={"Origin": ext_origin},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == ext_origin
