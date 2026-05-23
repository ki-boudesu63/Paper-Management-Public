"""Tests for to_vault_relative helper function.

Covers:
- Normal case: absolute path under vault -> forward-slash relative path
- Path outside vault -> fallback to filename only
- Empty vault_path -> fallback to filename only
- None note_path -> returns None
- Empty note_path -> returns empty string
- Windows backslash normalization
- Nested subdirectories
"""

from __future__ import annotations

from src.web.helpers import to_vault_relative


class TestToVaultRelative:
    """Tests for to_vault_relative path conversion."""

    def test_normal_case_returns_relative_posix_path(self) -> None:
        """Absolute path under vault returns forward-slash relative path."""
        abs_path = r"G:\マイドライブ\Obsidian Vault\20_paper_management\K\Kitano 2024 - Test.md"
        vault_path = r"G:\マイドライブ\Obsidian Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "20_paper_management/K/Kitano 2024 - Test.md"

    def test_forward_slash_input(self) -> None:
        """Paths with forward slashes are handled correctly."""
        abs_path = "G:/MyDrive/Vault/papers/A/Anderson 2025 - Review.md"
        vault_path = "G:/MyDrive/Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "papers/A/Anderson 2025 - Review.md"

    def test_mixed_slashes(self) -> None:
        """Mixed forward/back slashes are normalized."""
        abs_path = r"G:\MyDrive\Vault/papers\K/Kitano 2024 - Test.pdf"
        vault_path = r"G:\MyDrive\Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "papers/K/Kitano 2024 - Test.pdf"

    def test_path_outside_vault_returns_filename(self) -> None:
        """Path outside vault falls back to filename only."""
        abs_path = r"D:\other\folder\paper.md"
        vault_path = r"G:\マイドライブ\Obsidian Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "paper.md"

    def test_empty_vault_path_returns_filename(self) -> None:
        """Empty vault_path falls back to filename only."""
        abs_path = r"G:\some\path\paper.md"
        vault_path = ""
        result = to_vault_relative(abs_path, vault_path)
        assert result == "paper.md"

    def test_none_path_returns_none(self) -> None:
        """None input returns None."""
        result = to_vault_relative(None, r"G:\Vault")
        assert result is None

    def test_empty_string_path_returns_empty(self) -> None:
        """Empty string input returns empty string."""
        result = to_vault_relative("", r"G:\Vault")
        assert result == ""

    def test_deeply_nested_path(self) -> None:
        """Deeply nested path under vault returns full relative path."""
        abs_path = r"G:\Vault\a\b\c\d\paper.md"
        vault_path = r"G:\Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "a/b/c/d/paper.md"

    def test_vault_path_with_trailing_slash(self) -> None:
        """Vault path with trailing slash is handled."""
        abs_path = r"G:\Vault\papers\test.md"
        vault_path = r"G:\Vault\\"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "papers/test.md"

    def test_case_insensitive_on_windows(self) -> None:
        """Path matching is case-insensitive (Windows behavior)."""
        abs_path = r"g:\vault\papers\test.md"
        vault_path = r"G:\Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "papers/test.md"

    def test_pdf_path_conversion(self) -> None:
        """PDF paths are also converted correctly."""
        abs_path = r"G:\Vault\20_paper_management\M\Mizuno 2023 - Stem.pdf"
        vault_path = r"G:\Vault"
        result = to_vault_relative(abs_path, vault_path)
        assert result == "20_paper_management/M/Mizuno 2023 - Stem.pdf"

    def test_already_relative_path_returned_as_posix(self) -> None:
        """If path is already relative, return as-is with forward slashes."""
        rel_path = r"papers\K\Kitano 2024 - Test.md"
        vault_path = r"G:\Vault"
        # Not under vault (relative path can't be relative_to absolute vault)
        # Should fallback to filename
        result = to_vault_relative(rel_path, vault_path)
        assert result == "Kitano 2024 - Test.md"
