"""Tests for library routes: listing, search, initial-letter filter, obsidian URI.

Uses FastAPI TestClient with mocked LibraryAppService.
No real filesystem or network access.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from .conftest import SAMPLE_PAPERS

# ============================================================
# Library page (GET /)
# ============================================================


class TestLibraryPage:
    """Tests for the main library page."""

    def test_library_page_returns_200(self, client: TestClient) -> None:
        """GET / returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_library_page_contains_paper_titles(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET / renders paper titles in the response."""
        response = client.get("/")
        assert response.status_code == 200
        for paper in SAMPLE_PAPERS:
            assert paper.metadata.title in response.text

    def test_library_page_contains_initial_rail(
        self, client: TestClient
    ) -> None:
        """GET / includes the initial rail navigation."""
        response = client.get("/")
        assert response.status_code == 200
        assert "initial-rail" in response.text

    def test_library_page_contains_search_input(
        self, client: TestClient
    ) -> None:
        """GET / includes the search input field."""
        response = client.get("/")
        assert response.status_code == 200
        assert "search-input" in response.text

    def test_library_page_contains_obsidian_search_button(
        self, client: TestClient
    ) -> None:
        """GET / includes the Obsidian search button."""
        response = client.get("/")
        assert response.status_code == 200
        assert "obsidian-search-btn" in response.text

    def test_library_page_contains_nav_links(
        self, client: TestClient
    ) -> None:
        """GET / includes navigation links to the other screens.

        Regression: the library (home) page previously had no links to
        settings / import / collections, leaving it a dead end.
        """
        response = client.get("/")
        assert response.status_code == 200
        assert 'href="/settings"' in response.text
        assert 'href="/import"' in response.text
        assert 'href="/collections"' in response.text

    def test_library_page_contains_inspector_panel(
        self, client: TestClient
    ) -> None:
        """GET / includes the inspector panel area."""
        response = client.get("/")
        assert response.status_code == 200
        assert "inspector-panel" in response.text

    def test_library_page_filter_by_letter(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /?letter=K calls list_by_initial('K')."""
        kitano_paper = SAMPLE_PAPERS[0]
        mock_library_service.list_by_initial.return_value = [kitano_paper]

        response = client.get("/?letter=K")
        assert response.status_code == 200
        mock_library_service.list_by_initial.assert_called_with("K")

    def test_library_page_search_by_query(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /?q=tracheal calls fulltext_search."""
        mock_library_service.fulltext_search.return_value = [SAMPLE_PAPERS[0]]

        response = client.get("/?q=tracheal")
        assert response.status_code == 200
        mock_library_service.fulltext_search.assert_called_once_with("tracheal")

    def test_library_page_search_by_author_year_tag(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /?author=Mizuno&year=2023 calls search with author+year."""
        mock_library_service.search.return_value = [SAMPLE_PAPERS[1]]

        response = client.get("/?author=Mizuno&year=2023")
        assert response.status_code == 200
        mock_library_service.search.assert_called_once()
        call_args = mock_library_service.search.call_args[0][0]
        assert call_args.author == "Mizuno"
        assert call_args.year == 2023


# ============================================================
# Paper list partial (GET /papers)
# ============================================================


class TestPaperListPartial:
    """Tests for the paper list htmx partial."""

    def test_paper_list_returns_200(self, client: TestClient) -> None:
        """GET /papers returns 200."""
        response = client.get("/papers")
        assert response.status_code == 200

    def test_paper_list_filter_by_letter(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /papers?letter=A filters by initial letter."""
        anderson_paper = SAMPLE_PAPERS[2]
        mock_library_service.list_by_initial.return_value = [anderson_paper]

        response = client.get("/papers?letter=A")
        assert response.status_code == 200
        assert anderson_paper.metadata.title in response.text
        mock_library_service.list_by_initial.assert_called_with("A")

    def test_paper_list_search(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /papers?q=stem calls fulltext_search."""
        mock_library_service.fulltext_search.return_value = [SAMPLE_PAPERS[1]]

        response = client.get("/papers?q=stem")
        assert response.status_code == 200
        mock_library_service.fulltext_search.assert_called_once_with("stem")

    def test_paper_list_empty_state(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /papers with no results shows empty state."""
        mock_library_service.list_all.return_value = []

        response = client.get("/papers")
        assert response.status_code == 200
        assert "論文が見つかりません" in response.text


# ============================================================
# Inspector (GET /inspector/{paper_id})
# ============================================================


class TestInspector:
    """Tests for the inspector panel partial."""

    def test_inspector_returns_200_for_existing_paper(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /inspector/{id} returns 200 with paper details."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert response.status_code == 200
        assert paper.metadata.title in response.text

    def test_inspector_shows_authors(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Inspector shows author display names."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert paper.metadata.first_author.display_name in response.text

    def test_inspector_shows_doi(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Inspector shows DOI when present."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert paper.metadata.doi.value in response.text

    def test_inspector_shows_obsidian_buttons(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Inspector shows Obsidian open buttons."""
        paper = SAMPLE_PAPERS[0]
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert "obsidian-open-btn" in response.text
        assert "Obsidianで開く" in response.text
        assert "PDFを開く" in response.text

    def test_inspector_empty_state_for_missing_paper(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """GET /inspector/{id} for unknown paper shows empty state."""
        mock_library_service.get_by_id.return_value = None

        response = client.get("/inspector/nonexistent")
        assert response.status_code == 200
        assert "論文を選択してください" in response.text


# ============================================================
# Obsidian URI API (GET /api/obsidian/*)
# ============================================================


class TestObsidianURI:
    """Tests for obsidian:// URI generation endpoints."""

    def test_obsidian_open_uri_generation(
        self, client: TestClient
    ) -> None:
        """GET /api/obsidian/open generates correct URI."""
        response = client.get(
            "/api/obsidian/open",
            params={"file": "K/Kitano 2024 - Test.md"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "uri" in data
        assert data["uri"].startswith("obsidian://open?vault=TestVault")
        assert "K/Kitano" in data["uri"]

    def test_obsidian_open_uri_encodes_vault_name(
        self, client: TestClient
    ) -> None:
        """Vault name is URL-encoded in the URI."""
        response = client.get(
            "/api/obsidian/open",
            params={"file": "test.md"},
        )
        data = response.json()
        assert "TestVault" in data["uri"]

    def test_obsidian_search_uri_generation(
        self, client: TestClient
    ) -> None:
        """GET /api/obsidian/search generates correct URI."""
        response = client.get(
            "/api/obsidian/search",
            params={"q": "tracheal regeneration"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "uri" in data
        assert data["uri"].startswith("obsidian://search?vault=TestVault")
        assert "tracheal" in data["uri"]

    def test_obsidian_search_uri_encodes_query(
        self, client: TestClient
    ) -> None:
        """Search query is URL-encoded in the URI."""
        response = client.get(
            "/api/obsidian/search",
            params={"q": "test query with spaces"},
        )
        data = response.json()
        # Spaces should be percent-encoded
        assert "test%20query%20with%20spaces" in data["uri"]

    def test_obsidian_open_requires_file_param(
        self, client: TestClient
    ) -> None:
        """GET /api/obsidian/open without file param returns 422."""
        response = client.get("/api/obsidian/open")
        assert response.status_code == 422

    def test_obsidian_search_requires_query_param(
        self, client: TestClient
    ) -> None:
        """GET /api/obsidian/search without q param returns 422."""
        response = client.get("/api/obsidian/search")
        assert response.status_code == 422


# ============================================================
# Template rendering smoke tests
# ============================================================


class TestTemplateRendering:
    """Smoke tests to verify templates render without exceptions."""

    def test_base_template_structure(self, client: TestClient) -> None:
        """Library page includes expected HTML structure."""
        response = client.get("/")
        assert "<!DOCTYPE html>" in response.text
        assert "layout-container" in response.text

    def test_initial_rail_letters_present(
        self, client: TestClient
    ) -> None:
        """Initial rail contains all 26 letters plus #."""
        response = client.get("/")
        text = response.text
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            # The letter appears inside the rail anchor tag with possible whitespace
            assert f'title="{letter}"' in text, f"Letter {letter} not found in rail"
        assert 'title="#"' in text

    def test_google_fonts_loaded(self, client: TestClient) -> None:
        """Base template includes Google Fonts link."""
        response = client.get("/")
        assert "fonts.googleapis.com" in response.text
        assert "Shippori+Mincho" in response.text
        assert "BIZ+UDPGothic" in response.text
        assert "IBM+Plex+Sans" in response.text
        assert "IBM+Plex+Mono" in response.text

    def test_htmx_loaded(self, client: TestClient) -> None:
        """Base template includes htmx script."""
        response = client.get("/")
        assert "htmx.org" in response.text

    def test_design_tokens_loaded(self, client: TestClient) -> None:
        """Base template includes tokens.css."""
        response = client.get("/")
        assert "tokens.css" in response.text

    def test_components_css_loaded(self, client: TestClient) -> None:
        """Base template includes components.css."""
        response = client.get("/")
        assert "components.css" in response.text

    def test_app_js_loaded(self, client: TestClient) -> None:
        """Base template includes app.js."""
        response = client.get("/")
        assert "app.js" in response.text
