"""Tests for inspector route partial rendering."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.domain.collection import Collection, CollectionId

from .conftest import make_paper


class TestInspectorVaultRelativePaths:
    """Inspector buttons should use vault-relative paths for Obsidian."""

    def test_note_path_is_vault_relative(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """data-file for MD note should be vault-relative with forward slashes."""
        paper = make_paper(
            note_path="G:/TestVault/20_papers/K/Kitano 2024 - Test.md",
            pdf_path="G:/TestVault/20_papers/K/Kitano 2024 - Test.pdf",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert response.status_code == 200
        assert 'data-file="20_papers/K/Kitano 2024 - Test.md"' in response.text

    def test_pdf_path_is_vault_relative(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """data-file for PDF should be vault-relative with forward slashes."""
        paper = make_paper(
            note_path="G:/TestVault/papers/M/Mizuno 2023 - Stem.md",
            pdf_path="G:/TestVault/papers/M/Mizuno 2023 - Stem.pdf",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert response.status_code == 200
        assert 'data-file="papers/M/Mizuno 2023 - Stem.pdf"' in response.text

    def test_md_only_paper_shows_attach_pdf_action(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """A paper without PDF should show attach action and no PDF open button."""
        paper = make_paper(pdf_path=None)
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")

        assert response.status_code == 200
        assert "attach-pdf" in response.text
        assert "obsidian_pdf_path" not in response.text

    def test_path_outside_vault_falls_back_to_filename(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Path outside vault falls back to filename only."""
        paper = make_paper(
            note_path="D:/other/location/paper.md",
            pdf_path="D:/other/location/paper.pdf",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert response.status_code == 200
        assert 'data-file="paper.md"' in response.text
        assert 'data-file="paper.pdf"' in response.text

    def test_none_note_path_hides_button(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """None note_path means no MD open button."""
        paper = make_paper(
            note_path=None,
            pdf_path="G:/TestVault/papers/test.pdf",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert response.status_code == 200
        assert "PDFを開く" in response.text
        assert "Obsidianで開く" not in response.text
        assert response.text.count("obsidian-open-btn") == 1

    def test_backslash_paths_normalized_to_forward_slash(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        r"""Windows backslash paths are converted to forward slashes."""
        paper = make_paper(
            note_path=r"G:\TestVault\papers\K\Kitano 2024 - Test.md",
            pdf_path=r"G:\TestVault\papers\K\Kitano 2024 - Test.pdf",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")
        assert response.status_code == 200
        assert 'data-file="papers/K/Kitano 2024 - Test.md"' in response.text
        assert 'data-file="papers/K/Kitano 2024 - Test.pdf"' in response.text

    def test_collection_add_ui_is_rendered(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Inspector includes a collection selector when collections exist."""
        paper = make_paper()
        collection = Collection(id=CollectionId("coll-001"), name="Project A")
        mock_library_service.get_by_id.return_value = paper
        mock_collection_service.list_collections.return_value = [collection]
        mock_collection_service.list_collection_names_for_paper.return_value = [
            "Project A"
        ]

        response = client.get(f"/inspector/{paper.id.value}")

        assert response.status_code == 200
        assert "コレクション" in response.text
        assert "Project A" in response.text
        assert "追加" in response.text

    def test_collection_empty_guidance_is_rendered(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
        mock_collection_service: MagicMock,
    ) -> None:
        """Inspector guides users to create a collection when none exist."""
        paper = make_paper()
        mock_library_service.get_by_id.return_value = paper
        mock_collection_service.list_collections.return_value = []

        response = client.get(f"/inspector/{paper.id.value}")

        assert response.status_code == 200
        assert "先にコレクションを作成してください" in response.text

    def test_abstract_is_rendered(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Inspector displays abstract text when metadata has one."""
        paper = make_paper()
        paper.metadata = type(paper.metadata)(
            title=paper.metadata.title,
            authors=paper.metadata.authors,
            year=paper.metadata.year,
            doi=paper.metadata.doi,
            abstract="This is the abstract text.",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")

        assert response.status_code == 200
        assert "Abstract" in response.text
        assert "This is the abstract text." in response.text

    def test_memo_is_rendered(
        self,
        client: TestClient,
        mock_library_service: MagicMock,
    ) -> None:
        """Inspector displays memo text when metadata has one."""
        paper = make_paper()
        paper.metadata = type(paper.metadata)(
            title=paper.metadata.title,
            authors=paper.metadata.authors,
            year=paper.metadata.year,
            doi=paper.metadata.doi,
            memo="Journal club note.",
        )
        mock_library_service.get_by_id.return_value = paper

        response = client.get(f"/inspector/{paper.id.value}")

        assert response.status_code == 200
        assert "メモ" in response.text
        assert "Journal club note." in response.text
