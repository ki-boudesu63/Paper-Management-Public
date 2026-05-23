"""Tests for collections routes.

Uses FastAPI TestClient with mocked CollectionAppService.
No real filesystem or network access.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.domain.collection import Collection, CollectionId
from tests.web.conftest import SAMPLE_PAPERS

SAMPLE_COLLECTIONS = [
    Collection(id=CollectionId("coll-001"), name="Tracheal Regeneration Project"),
    Collection(id=CollectionId("coll-002"), name="Stem Cell Review"),
]


class TestCollectionsPage:
    """Tests for the collections management page."""

    def test_collections_page_returns_200(self, client: TestClient) -> None:
        """GET /collections returns 200 OK."""
        response = client.get("/collections")
        assert response.status_code == 200

    def test_collections_page_contains_heading(self, client: TestClient) -> None:
        """GET /collections renders the page heading."""
        response = client.get("/collections")
        assert "コレクション管理" in response.text

    def test_collections_page_shows_collections(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """GET /collections displays collection names when present."""
        mock_collection_service.list_collections.return_value = SAMPLE_COLLECTIONS

        response = client.get("/collections")
        assert response.status_code == 200
        assert "Tracheal Regeneration Project" in response.text
        assert "Stem Cell Review" in response.text

    def test_collections_page_empty_state(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """GET /collections with no collections shows empty state."""
        mock_collection_service.list_collections.return_value = []

        response = client.get("/collections")
        assert response.status_code == 200
        assert "コレクションがありません" in response.text

    def test_collections_page_has_create_form(self, client: TestClient) -> None:
        """GET /collections includes the create collection form."""
        response = client.get("/collections")
        assert 'action="/collections/create"' in response.text
        assert 'name="name"' in response.text

    def test_collections_page_has_nav_links(self, client: TestClient) -> None:
        """GET /collections has navigation links to other pages."""
        response = client.get("/collections")
        assert 'href="/"' in response.text
        assert 'href="/import"' in response.text
        assert 'href="/settings"' in response.text

    def test_collections_page_has_inspector_panel(
        self,
        client: TestClient,
    ) -> None:
        """Collections page includes the same inspector target as the library."""
        response = client.get("/collections")

        assert response.status_code == 200
        assert 'id="inspector-panel"' in response.text


class TestCreateCollection:
    """Tests for collection creation."""

    def test_create_collection_redirects(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """POST /collections/create redirects to /collections."""
        response = client.post(
            "/collections/create",
            data={"name": "New Project"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/collections"

    def test_create_collection_calls_service(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """POST /collections/create calls create_collection on service."""
        client.post(
            "/collections/create",
            data={"name": "New Project"},
            follow_redirects=False,
        )
        mock_collection_service.create_collection.assert_called_once_with("New Project")


class TestDeleteCollection:
    """Tests for collection deletion."""

    def test_delete_collection_redirects(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """POST /collections/{id}/delete redirects to /collections."""
        response = client.post(
            "/collections/coll-001/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/collections"

    def test_delete_collection_calls_service(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """POST /collections/{id}/delete calls delete_collection."""
        client.post(
            "/collections/coll-001/delete",
            follow_redirects=False,
        )
        mock_collection_service.delete_collection.assert_called_once_with("coll-001")

    def test_delete_nonexistent_collection_still_redirects(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """Deleting a non-existent collection redirects gracefully."""
        mock_collection_service.delete_collection.side_effect = KeyError("not found")

        response = client.post(
            "/collections/nonexistent/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestCollectionPapers:
    """Tests for collection paper detail partials."""

    def test_collection_papers_returns_200(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """GET /collections/{id}/papers returns the detail partial."""
        collection = SAMPLE_COLLECTIONS[0]
        mock_collection_service.get_collection.return_value = collection
        mock_collection_service.list_papers_in_collection.return_value = [
            SAMPLE_PAPERS[0]
        ]

        response = client.get(f"/collections/{collection.id.value}/papers")

        assert response.status_code == 200
        assert collection.name in response.text
        assert SAMPLE_PAPERS[0].metadata.title in response.text

    def test_collection_paper_row_targets_inspector(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """Clicking a collection paper row loads the standard inspector partial."""
        collection = SAMPLE_COLLECTIONS[0]
        paper = SAMPLE_PAPERS[0]
        mock_collection_service.get_collection.return_value = collection
        mock_collection_service.list_papers_in_collection.return_value = [paper]

        response = client.get(f"/collections/{collection.id.value}/papers")

        assert response.status_code == 200
        assert f'hx-get="/inspector/{paper.id.value}"' in response.text
        assert 'hx-target="#inspector-panel"' in response.text

    def test_collection_papers_empty_state(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """Collection detail shows an empty state when no papers are present."""
        collection = SAMPLE_COLLECTIONS[0]
        mock_collection_service.get_collection.return_value = collection
        mock_collection_service.list_papers_in_collection.return_value = []

        response = client.get(f"/collections/{collection.id.value}/papers")

        assert response.status_code == 200
        assert "論文がありません" in response.text


class TestCollectionPaperActions:
    """Tests for adding and removing papers from collections."""

    def test_add_paper_to_collection_calls_service(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """POST add route adds the selected paper to the collection."""
        response = client.post(
            "/collections/coll-001/papers/10.1234/test.001/add",
        )

        assert response.status_code == 204
        mock_collection_service.add_paper_to_collection.assert_called_once_with(
            "coll-001",
            "10.1234/test.001",
        )
        assert "HX-Trigger" in response.headers

    def test_add_paper_to_selected_collection_calls_service(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """Inspector form add route accepts collection_id from form data."""
        response = client.post(
            "/collections/papers/10.1234/test.001/add",
            data={"collection_id": "coll-001"},
        )

        assert response.status_code == 204
        mock_collection_service.add_paper_to_collection.assert_called_once_with(
            "coll-001",
            "10.1234/test.001",
        )

    def test_remove_paper_from_collection_updates_partial(
        self,
        client: TestClient,
        mock_collection_service: MagicMock,
    ) -> None:
        """POST remove route returns the refreshed collection paper list."""
        collection = SAMPLE_COLLECTIONS[0]
        mock_collection_service.get_collection.return_value = collection
        mock_collection_service.remove_paper_from_collection.return_value = collection
        mock_collection_service.list_papers_in_collection.return_value = []

        response = client.post(
            "/collections/coll-001/papers/10.1234/test.001/remove",
        )

        assert response.status_code == 200
        mock_collection_service.remove_paper_from_collection.assert_called_once_with(
            "coll-001",
            "10.1234/test.001",
        )
        assert "論文がありません" in response.text
